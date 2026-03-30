from pydantic import BaseModel, Field
from typing import Optional


class AnalysisRequest(BaseModel):
    """Incoming request from Agent System A via HTTP POST /analyze."""
    location: str
    property_type: str = "Apartment"
    bedrooms: Optional[int] = None
    budget_max: Optional[float] = None
    furnished: Optional[str] = None
    query: str = ""


class ParsedCriteria(BaseModel):
    """Structured criteria passed to comp finder."""
    location: str
    property_type: str
    bedrooms: Optional[int] = None
    budget_max: Optional[float] = None
    furnished: Optional[str] = None
    search_strategy: str = Field(
        default="",
        description="Human-readable search plan for comp finder",
    )


def parse_request(request: AnalysisRequest) -> ParsedCriteria:
    """Parse incoming request into structured search criteria."""
    filters = []

    if request.bedrooms:
        filters.append(f"{request.bedrooms}-bedroom")

    filters.append(request.property_type)
    filters.append(f"in {request.location}")

    if request.budget_max:
        filters.append(f"under AED {request.budget_max:,.0f}")

    if request.furnished:
        filters.append(request.furnished.lower())

    strategy = f"Find comparable {' '.join(filters)}"

    return ParsedCriteria(
        location=request.location,
        property_type=request.property_type,
        bedrooms=request.bedrooms,
        budget_max=request.budget_max,
        furnished=request.furnished,
        search_strategy=strategy,
    )
