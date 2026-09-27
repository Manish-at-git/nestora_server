"""Idempotent insertion of the platform's reference geography."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.location_data.locations import COUNTRIES, INDIA_MAJOR_CITIES, MAJOR_WORLD_CITIES
from app.modules.locations.models import City, Country, District, Region


async def _upsert_country(
    session: AsyncSession, iso2_code: str, iso3_code: str, name: str, currency_code: str
) -> Country:
    country = await session.scalar(select(Country).where(Country.iso2_code == iso2_code))
    if country is None:
        country = Country(iso2_code=iso2_code, iso3_code=iso3_code, name=name, currency_code=currency_code)
        session.add(country)
        await session.flush()
        return country
    country.iso3_code, country.name, country.currency_code = iso3_code, name, currency_code
    return country


async def _upsert_region(
    session: AsyncSession, country_id: str, code: str, name: str, kind: str
) -> Region:
    region = await session.scalar(
        select(Region).where(Region.country_id == country_id, Region.code == code)
    )
    if region is None:
        region = Region(country_id=country_id, code=code, name=name, kind=kind)
        session.add(region)
        await session.flush()
        return region
    region.name, region.kind = name, kind
    return region


async def _upsert_district(
    session: AsyncSession, region_id: str, code: str, name: str, kind: str = "DISTRICT"
) -> District:
    district = await session.scalar(
        select(District).where(District.region_id == region_id, District.code == code)
    )
    if district is None:
        district = District(region_id=region_id, code=code, name=name, kind=kind)
        session.add(district)
        await session.flush()
        return district
    district.name, district.kind = name, kind
    return district


async def _upsert_city(
    session: AsyncSession, region_id: str, district_id: str | None, name: str
) -> City:
    city = await session.scalar(
        select(City).where(
            City.region_id == region_id,
            City.district_id == district_id,
            City.name == name,
        )
    )
    if city is None:
        city = City(region_id=region_id, district_id=district_id, name=name)
        session.add(city)
        await session.flush()
    return city


def validate_india_dataset(rows: object) -> list[dict]:
    """Fail early if the pinned source changes shape or contains incomplete rows."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("India location dataset must be a non-empty list")
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) and row[key] for key in ("code", "name")):
            raise ValueError("Every India region must have a code and name")
        if not isinstance(row.get("districts"), list):
            raise ValueError(f"India region {row['code']} has no district list")
        for district in row["districts"]:
            if not isinstance(district, dict) or not all(
                isinstance(district.get(key), str) and district[key] for key in ("code", "name")
            ):
                raise ValueError(f"India region {row['code']} has an invalid district")
    return rows


async def seed_locations(session: AsyncSession, india_rows: object) -> dict[str, int]:
    """Insert or update all location records without deleting operator-added data."""
    india_rows = validate_india_dataset(india_rows)
    countries = {
        iso2: await _upsert_country(session, iso2, iso3, name, currency)
        for iso2, iso3, name, currency in COUNTRIES
    }
    region_by_key: dict[tuple[str, str], Region] = {}
    district_by_key: dict[tuple[str, str, str], District] = {}

    for row in india_rows:
        region = await _upsert_region(session, countries["IN"].id, row["code"], row["name"], "UNION_TERRITORY" if row["code"] in {"AN", "CH", "DH", "DL", "JK", "LA", "LD", "PY"} else "STATE")
        region_by_key[("IN", row["code"])] = region
        for district_row in row["districts"]:
            district = await _upsert_district(session, region.id, district_row["code"], district_row["name"])
            district_by_key[("IN", row["code"], district_row["code"])] = district

    for country_code, region_code, region_name, region_kind, district_code, district_name, city_name in MAJOR_WORLD_CITIES:
        region = await _upsert_region(session, countries[country_code].id, region_code, region_name, region_kind)
        district = await _upsert_district(session, region.id, district_code, district_name, "ADMINISTRATIVE_AREA")
        await _upsert_city(session, region.id, district.id, city_name)

    missing_city_districts: list[str] = []
    for region_code, district_code, city_name in INDIA_MAJOR_CITIES:
        region = region_by_key.get(("IN", region_code))
        district = district_by_key.get(("IN", region_code, district_code))
        if region is None or district is None:
            missing_city_districts.append(f"{region_code}/{district_code} ({city_name})")
            continue
        await _upsert_city(session, region.id, district.id, city_name)
    if missing_city_districts:
        raise ValueError("Pinned India dataset is missing city mappings: " + ", ".join(missing_city_districts))

    return {
        "countries": len(COUNTRIES),
        "regions": len(region_by_key) + len({(row[0], row[1]) for row in MAJOR_WORLD_CITIES}),
        "districts": len(district_by_key) + len({row[:5] for row in MAJOR_WORLD_CITIES}),
        "cities": len(INDIA_MAJOR_CITIES) + len(MAJOR_WORLD_CITIES),
    }
