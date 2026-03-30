import pandas as pd
from qdrant_client import QdrantClient
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Optional

from agent_system_b.config import (
    QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL, CSV_PATH,
)
from agent_system_b.pipeline.request_parser import ParsedCriteria


# --- Pydantic models for clean output ---

class ComparableProperty(BaseModel):
    """A single comparable property from the CSV."""
    address: str
    rent: float
    beds: Optional[int] = None
    baths: Optional[int] = None
    property_type: str
    area_sqft: Optional[float] = None
    rent_per_sqft: Optional[float] = None
    location: str
    city: str
    furnished: Optional[str] = None


class CompFinderResult(BaseModel):
    """Combined result from CSV + Qdrant search."""
    comparable_properties: List[ComparableProperty] = []
    market_context: List[str] = []
    num_comps_found: Optional[int] = None

    def model_post_init(self, __context):
        if self.num_comps_found is None:
            self.num_comps_found = len(self.comparable_properties)


# --- Initialize clients ---
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
openai_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
df = pd.read_csv(CSV_PATH)


def find_comps(criteria: ParsedCriteria, top_n: int = 10) -> CompFinderResult:
    """Find comparable properties from CSV + market context from Qdrant."""
    properties = _search_csv(criteria, top_n)
    market_context = _search_qdrant(criteria.search_strategy)

    return CompFinderResult(
        comparable_properties=properties,
        market_context=market_context,
        num_comps_found=len(properties),
    )


def _search_csv(criteria: ParsedCriteria, top_n: int = 10) -> List[ComparableProperty]:
    """Filter CSV with pandas based on structured criteria."""
    filtered = df.copy()

    # --- Apply filters progressively ---

    # Location (case-insensitive partial match)
    if criteria.location:
        mask = (
            filtered["Location"].str.contains(criteria.location, case=False, na=False)
            | filtered["City"].str.contains(criteria.location, case=False, na=False)
        )
        filtered = filtered[mask]

    # Property type
    if criteria.property_type:
        filtered = filtered[
            filtered["Type"].str.contains(criteria.property_type, case=False, na=False)
        ]

    # Bedrooms (exact match)
    if criteria.bedrooms is not None:
        filtered = filtered[filtered["Beds"] == criteria.bedrooms]

    # Budget (less than or equal)
    if criteria.budget_max is not None:
        filtered = filtered[filtered["Rent"] <= criteria.budget_max]

    # Furnished status
    if criteria.furnished is not None:
        filtered = filtered[
            filtered["Furnishing"].str.contains(criteria.furnished, case=False, na=False)
        ]

    # --- Sort by rent (closest to budget if given, otherwise ascending) ---
    if criteria.budget_max:
        filtered = filtered.sort_values(
            by="Rent", key=lambda x: abs(x - criteria.budget_max), ascending=True
        )
    else:
        filtered = filtered.sort_values(by="Rent", ascending=True)

    # --- Take top N and convert to Pydantic models ---
    results = []
    for _, row in filtered.head(top_n).iterrows():
        results.append(
            ComparableProperty(
                address=str(row.get("Address", "")),
                rent=float(row.get("Rent", 0)),
                beds=int(row["Beds"]) if pd.notna(row.get("Beds")) else None,
                baths=int(row["Baths"]) if pd.notna(row.get("Baths")) else None,
                property_type=str(row.get("Type", "")),
                area_sqft=float(row["Area_in_sqft"]) if pd.notna(row.get("Area_in_sqft")) else None,
                rent_per_sqft=float(row["Rent_per_sqft"]) if pd.notna(row.get("Rent_per_sqft")) else None,
                location=str(row.get("Location", "")),
                city=str(row.get("City", "")),
                furnished=str(row.get("Furnishing", "")),
            )
        )

    return results


def _search_qdrant(query: str, top_k: int = 5) -> List[str]:
    """Semantic search on PDF market reports in Qdrant."""
    try:
        # Embed the query
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query],
        )
        query_vector = response.data[0].embedding

        # Search Qdrant
        response_qdrant = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
        )

        return [hit.payload["text"] for hit in response_qdrant.points if hit.payload]
    except Exception:
        return []
