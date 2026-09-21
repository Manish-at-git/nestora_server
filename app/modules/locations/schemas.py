"""Read contracts for normalized reference geography."""

from pydantic import BaseModel


class CountryResponse(BaseModel):
    id: str
    name: str
    iso2_code: str


class RegionResponse(BaseModel):
    id: str
    country_id: str
    name: str
    kind: str


class CityResponse(BaseModel):
    id: str
    region_id: str
    district_id: str | None = None
    name: str
