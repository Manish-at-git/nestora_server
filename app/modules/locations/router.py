"""Authenticated lookup endpoints for dependent address selects."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_auth_context
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.modules.locations.models import City, Country, Region
from app.modules.locations.schemas import CityResponse, CountryResponse, RegionResponse


router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/countries", response_model=ApiResponse[list[CountryResponse]])
async def list_countries(
    _: object = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)
) -> dict:
    rows = (await session.scalars(select(Country).order_by(Country.name))).all()
    return success_response([CountryResponse(id=row.id, name=row.name, iso2_code=row.iso2_code) for row in rows])


@router.get("/regions", response_model=ApiResponse[list[RegionResponse]])
async def list_regions(
    country_id: str,
    _: object = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = (await session.scalars(select(Region).where(Region.country_id == country_id).order_by(Region.name))).all()
    return success_response([RegionResponse(id=row.id, country_id=row.country_id, name=row.name, kind=row.kind) for row in rows])


@router.get("/cities", response_model=ApiResponse[list[CityResponse]])
async def list_cities(
    region_id: str,
    _: object = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = (await session.scalars(select(City).where(City.region_id == region_id).order_by(City.name))).all()
    return success_response([CityResponse(id=row.id, region_id=row.region_id, district_id=row.district_id, name=row.name) for row in rows])
