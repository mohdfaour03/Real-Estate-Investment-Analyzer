"""
RAG Tool — Searches CSV (pandas), Qdrant (PDFs), and the web for property data.

Used by both Property Analyst and Market Researcher agents.
"""

import pandas as pd
from openai import OpenAI
from qdrant_client import QdrantClient
from duckduckgo_search import DDGS
from langchain_core.tools import tool

from agent_system_a.config import (
    QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL, CSV_PATH,
)
from shared.logging_config import get_logger

logger = get_logger("agent_system_a.rag_tools")


# --- Initialize once at module level ---
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
openai_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def get_available_documents() -> list[str]:
    """Query Qdrant for all unique document source names in the collection.
    Used to build dynamic system prompts so agents know what's in the knowledge base."""
    try:
        results = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=["source"],
            with_vectors=False,
        )
        sources = {point.payload.get("source", "") for point in results[0]}
        sources.discard("")
        return sorted(sources)
    except Exception as e:
        logger.warning(f"Could not list documents from Qdrant: {type(e).__name__}: {e}")
        return []

try:
    df = pd.read_csv(CSV_PATH)
    logger.info(f"CSV loaded | rows={len(df)} | path={CSV_PATH}")
except FileNotFoundError:
    logger.error(f"CSV file not found at {CSV_PATH} — property search will be unavailable")
    df = pd.DataFrame()
except Exception as e:
    logger.error(f"Failed to load CSV | error={type(e).__name__}: {e}")
    df = pd.DataFrame()


@tool
def search_properties(
    city: str = "",
    property_type: str = "",
    bedrooms: int = None,
    min_rent: float = None,
    max_rent: float = None,
    location: str = "",
    furnished: str = "",
    limit: int = 10,
) -> str:
    """Search UAE rental property listings with structured filters.

    Use this to find specific properties matching criteria like city,
    type, bedrooms, price range, location, and furnishing status.
    Returns matching listings as formatted text.
    """
    logger.info(f"search_properties called | city={city}, type={property_type}, beds={bedrooms}, rent={min_rent}-{max_rent}, location={location}")
    # Filter directly — no .copy() needed since we only read, never mutate the source
    filtered = df

    if city:
        filtered = filtered[filtered["City"].str.contains(city, case=False, na=False)]

    if property_type:
        filtered = filtered[filtered["Type"].str.contains(property_type, case=False, na=False)]

    if bedrooms is not None:
        filtered = filtered[filtered["Beds"] == bedrooms]

    if min_rent is not None:
        filtered = filtered[filtered["Rent"] >= min_rent]

    if max_rent is not None:
        filtered = filtered[filtered["Rent"] <= max_rent]

    if location:
        filtered = filtered[filtered["Location"].str.contains(location, case=False, na=False)]

    if furnished:
        filtered = filtered[filtered["Furnishing"].str.contains(furnished, case=False, na=False)]

    # Sort by rent ascending
    filtered = filtered.sort_values("Rent", ascending=True).head(limit)

    if filtered.empty:
        logger.warning(f"search_properties returned 0 results | city={city}, beds={bedrooms}")
        return "No properties found matching the given criteria."

    logger.info(f"search_properties found {len(filtered)} results")
    # Format results as readable text for the LLM
    results = []
    for _, row in filtered.iterrows():
        results.append(
            f"- {row['Address']}\n"
            f"  Rent: AED {row['Rent']:,.0f}/year | "
            f"Beds: {row['Beds']} | Baths: {row['Baths']} | "
            f"Type: {row['Type']} | Area: {row['Area_in_sqft']:,.0f} sqft | "
            f"Location: {row['Location']}, {row['City']} | "
            f"Furnished: {row['Furnishing']}"
        )

    return f"Found {len(filtered)} properties:\n\n" + "\n\n".join(results)


@tool
def search_market_reports(query: str, top_k: int = 5) -> str:
    """Search PDF market reports for insights about UAE real estate trends.

    Use this to find market analysis, rental trends, price forecasts,
    and area-specific insights from professional reports (DLD, CBRE, Knight Frank).
    """
    logger.info(f"search_market_reports called | query='{query[:60]}...' top_k={top_k}")
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
        results = response_qdrant.points
    except Exception as e:
        logger.error(f"search_market_reports failed | error={type(e).__name__}: {e}")
        return "Market report search is temporarily unavailable (Qdrant not reachable)."

    if not results:
        return "No relevant market reports found."

    # Format results
    passages = []
    for i, hit in enumerate(results, 1):
        source = hit.payload.get("source", "Unknown")
        text = hit.payload.get("text", "")
        score = hit.score
        passages.append(f"[{i}] (Source: {source}, Relevance: {score:.2f})\n{text}")

    return "\n\n---\n\n".join(passages)


@tool
def get_area_statistics(
    city: str = "",
    location: str = "",
    property_type: str = "",
) -> str:
    """Get aggregate statistics for a specific area — average rent, median rent,
    price range, number of listings, and rent per sqft.

    Use this for market overview and comparison between areas.
    """
    # Filter directly — no .copy() needed since we only read, never mutate the source
    filtered = df

    if city:
        filtered = filtered[filtered["City"].str.contains(city, case=False, na=False)]

    if location:
        filtered = filtered[filtered["Location"].str.contains(location, case=False, na=False)]

    if property_type:
        filtered = filtered[filtered["Type"].str.contains(property_type, case=False, na=False)]

    if filtered.empty:
        return "No data found for the specified area."

    stats = {
        "total_listings": len(filtered),
        "avg_rent": round(filtered["Rent"].mean(), 2),
        "median_rent": round(filtered["Rent"].median(), 2),
        "min_rent": round(filtered["Rent"].min(), 2),
        "max_rent": round(filtered["Rent"].max(), 2),
        "avg_area_sqft": round(filtered["Area_in_sqft"].mean(), 2),
        "avg_rent_per_sqft": round(filtered["Rent_per_sqft"].mean(), 2),
    }

    # Breakdown by bedrooms
    bed_breakdown = filtered.groupby("Beds")["Rent"].agg(["mean", "count"]).round(0)

    result = (
        f"Area Statistics:\n"
        f"  Total listings: {stats['total_listings']}\n"
        f"  Average rent: AED {stats['avg_rent']:,.0f}/year\n"
        f"  Median rent: AED {stats['median_rent']:,.0f}/year\n"
        f"  Rent range: AED {stats['min_rent']:,.0f} – {stats['max_rent']:,.0f}\n"
        f"  Avg area: {stats['avg_area_sqft']:,.0f} sqft\n"
        f"  Avg rent/sqft: AED {stats['avg_rent_per_sqft']:,.1f}\n\n"
        f"Breakdown by bedrooms:\n"
    )

    for beds, row in bed_breakdown.iterrows():
        result += f"  {int(beds)} bed: AED {row['mean']:,.0f} avg ({int(row['count'])} listings)\n"

    return result


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for any current or real-time information.

    Use this for: today's date, current news, events, regulations, market updates,
    or anything requiring up-to-date information beyond the local database.
    Pass the user's query directly — do not modify it.
    """
    import os
    import httpx as _httpx

    logger.info(f"web_search called | query='{query[:60]}...'")

    serpapi_key = os.getenv("SERPAPI_KEY", "")

    try:
        resp = _httpx.get("https://serpapi.com/search", params={
            "q": query,
            "api_key": serpapi_key,
            "engine": "google",
            "num": max_results,
        }, timeout=10)
        data = resp.json()
    except Exception as e:
        logger.error(f"web_search (SerpApi) failed | error={type(e).__name__}: {e}")
        # Fallback to DuckDuckGo
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region="wt-wt", max_results=max_results))
            if not results:
                return "No web results found."
            return "\n\n".join(f"[{i}] {r['title']}\n    {r['body']}" for i, r in enumerate(results, 1))
        except Exception as e2:
            return f"Web search failed: {e2}"

    formatted = []

    # Answer box (instant answers like today's date)
    if "answer_box" in data:
        ab = data["answer_box"]
        answer = ab.get("answer") or ab.get("snippet") or ab.get("result", "")
        if answer:
            formatted.append(f"[Answer] {answer}")

    # Knowledge graph
    if "knowledge_graph" in data:
        kg = data["knowledge_graph"]
        desc = kg.get("description", "")
        if desc:
            formatted.append(f"[Knowledge] {kg.get('title', '')}: {desc}")

    # Organic results
    for i, r in enumerate(data.get("organic_results", [])[:max_results], 1):
        formatted.append(f"[{i}] {r.get('title', '')}\n    {r.get('snippet', '')}\n    Source: {r.get('link', '')}")

    if not formatted:
        return "No web results found for this query."

    return "\n\n".join(formatted)
