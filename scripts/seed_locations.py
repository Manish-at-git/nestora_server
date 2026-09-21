"""Seed the normalized country, region, district, and city reference data."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from app.db.session import close_database, session_factory
from app.location_data.locations import INDIA_DATASET_SHA256, INDIA_DATASET_URL
from app.location_seed import seed_locations, validate_india_dataset


def load_india_dataset(source_file: str | None) -> list[dict]:
    """Load a checked-in operator file or the immutable public source snapshot."""
    if source_file:
        payload = Path(source_file).read_bytes()
    else:
        with urlopen(INDIA_DATASET_URL, timeout=30) as response:  # noqa: S310 - fixed HTTPS source and checksum
            payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != INDIA_DATASET_SHA256:
        raise ValueError("India dataset checksum does not match the pinned source")
    return validate_india_dataset(json.loads(payload))


async def main(source_file: str | None) -> None:
    """Run the seed in one transaction so incomplete geography is never committed."""
    try:
        india_rows = load_india_dataset(source_file)
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_locations(session, india_rows)
        print(
            "Seeded location reference data: "
            f"{counts['countries']} countries, {counts['regions']} regions, "
            f"{counts['districts']} districts, and {counts['cities']} cities."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--india-data-file",
        help="Path to the exact pinned India JSON snapshot for an offline seed run.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.india_data_file))
