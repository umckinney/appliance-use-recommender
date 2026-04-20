"""
Ingest NREL/OpenEI residential electricity rate data by ZIP code.

Downloads IOU (investor-owned utility) and non-IOU CSVs from OpenEI,
upserts utility and zipcode_utility rows, and writes a RateIngestionRun audit record.

Idempotent: skips download + upsert when source file SHA256 hasn't changed.

Usage:
    python -m scripts.ingest_zipcode_rates [--force]

Options:
    --force    Re-ingest even if SHA256 matches last run.

Environment:
    DATABASE_URL — defaults to sqlite+aiosqlite:///./flowshift.db
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Add project root to path so backend imports work when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models import (
    Base,
    RateIngestionRun,
    UtilityRecord,
    ZipCentroid,
    ZipcodeUtility,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# OpenEI residential rate CSVs (2022 edition — update URL for newer editions)
OPENEI_IOU_URL = "https://data.openei.org/files/6225/iou_zipcodes_2023.csv"
OPENEI_NONIOU_URL = "https://data.openei.org/files/6225/non_iou_zipcodes_2023.csv"

SOURCE_YEAR = 2022

# Census ZCTA Gazetteer — public domain, ZIP centroid lat/lng
CENSUS_GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/"
    "2023_Gaz_zcta_national.zip"
)

# CSV column names (OpenEI format)
# zip, eiaid, utility_name, state, service_type, ownership, comm_rate, ind_rate, res_rate
_COL_ZIP = "zip"
_COL_EIA_ID = "eiaid"
_COL_NAME = "utility_name"
_COL_STATE = "state"
_COL_OWNERSHIP = "ownership"
_COL_RES_RATE = "res_rate"


async def _fetch_csv(url: str, client: httpx.AsyncClient) -> tuple[str, str]:
    """Fetch CSV text and return (content, sha256_hex)."""
    log.info("Downloading %s", url)
    resp = await client.get(url, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    content = resp.text
    sha256 = hashlib.sha256(content.encode()).hexdigest()
    return content, sha256


def _last_sha256(runs: list[RateIngestionRun], source: str) -> str | None:
    for run in sorted(runs, key=lambda r: r.started_at, reverse=True):
        if run.source == source and run.status == "success" and run.source_version:
            return run.source_version
    return None


def _parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        # Normalise keys: strip whitespace and lower-case
        rows.append({k.strip().lower(): v.strip() for k, v in row.items()})
    return rows


async def _ingest_source(
    session: AsyncSession,
    source_name: str,
    url: str,
    client: httpx.AsyncClient,
    force: bool,
) -> None:
    started = datetime.now(UTC).replace(tzinfo=None)
    run = RateIngestionRun(source=source_name, started_at=started, status="running")
    session.add(run)
    await session.flush()

    try:
        content, sha256 = await _fetch_csv(url, client)

        # Skip if unchanged
        if not force:
            result = await session.execute(
                select(RateIngestionRun)
                .where(RateIngestionRun.source == source_name)
                .where(RateIngestionRun.status == "success")
                .where(RateIngestionRun.source_version == sha256)
            )
            if result.scalar_one_or_none():
                log.info("%s: SHA256 unchanged — skipping", source_name)
                run.status = "skipped"
                run.completed_at = datetime.now(UTC).replace(tzinfo=None)
                run.source_version = sha256
                return

        rows = _parse_csv(content)
        processed = inserted = updated = failed = 0

        for row in rows:
            processed += 1
            try:
                raw_eia_id = row.get(_COL_EIA_ID, "").strip()
                if not raw_eia_id:
                    failed += 1
                    continue
                eia_id = int(raw_eia_id)
                zipcode = row.get(_COL_ZIP, "").strip().zfill(5)
                if not zipcode or zipcode == "00000":
                    failed += 1
                    continue

                utility_name = row.get(_COL_NAME, "").strip() or f"Utility {eia_id}"
                state = (row.get(_COL_STATE, "") or "").strip()[:2] or None
                ownership = (row.get(_COL_OWNERSHIP, "") or "").strip() or None

                raw_rate = row.get(_COL_RES_RATE, "") or ""
                try:
                    res_rate: float | None = float(raw_rate) if raw_rate.strip() else None
                except ValueError:
                    res_rate = None

                # Upsert UtilityRecord
                util_result = await session.execute(
                    select(UtilityRecord).where(UtilityRecord.eia_id == eia_id)
                )
                util = util_result.scalar_one_or_none()
                if util is None:
                    util = UtilityRecord(
                        eia_id=eia_id,
                        name=utility_name,
                        state=state,
                        ownership_type=ownership,
                    )
                    session.add(util)
                    inserted += 1
                else:
                    util.name = utility_name
                    util.state = state
                    util.ownership_type = ownership
                    updated += 1

                # Upsert ZipcodeUtility
                zip_result = await session.execute(
                    select(ZipcodeUtility).where(
                        ZipcodeUtility.zipcode == zipcode,
                        ZipcodeUtility.eia_id == eia_id,
                    )
                )
                zcu = zip_result.scalar_one_or_none()
                if zcu is None:
                    zcu = ZipcodeUtility(
                        zipcode=zipcode,
                        eia_id=eia_id,
                        residential_rate_avg=res_rate,
                        source_year=SOURCE_YEAR,
                    )
                    session.add(zcu)
                else:
                    zcu.residential_rate_avg = res_rate
                    zcu.source_year = SOURCE_YEAR

            except Exception as exc:
                log.debug("Row error: %s — %s", row, exc)
                failed += 1

        # Mark primary utility per ZIP (the one with highest EIA ID for determinism)
        await session.flush()
        await session.execute(text("UPDATE zipcode_utility SET is_primary = false"))
        await session.execute(
            text(
                """
                UPDATE zipcode_utility SET is_primary = true
                WHERE (zipcode, eia_id) IN (
                    SELECT zipcode, MAX(eia_id)
                    FROM zipcode_utility
                    GROUP BY zipcode
                )
                """
            )
        )

        run.status = "success"
        run.records_processed = processed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_failed = failed
        run.source_version = sha256
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        log.info(
            "%s: processed=%d inserted=%d updated=%d failed=%d",
            source_name,
            processed,
            inserted,
            updated,
            failed,
        )

    except Exception as exc:
        run.status = "failed"
        run.error_log = str(exc)
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        log.error("%s: FAILED — %s", source_name, exc)
        raise


async def _ingest_centroids(session: AsyncSession, client: httpx.AsyncClient, force: bool) -> None:
    """Download Census Gazetteer and upsert zip_centroid rows. Idempotent."""
    source_name = "census_gazetteer"
    started = datetime.now(UTC).replace(tzinfo=None)
    run = RateIngestionRun(source=source_name, started_at=started, status="running")
    session.add(run)
    await session.flush()

    try:
        import io as _io
        import zipfile as _zipfile

        log.info("Downloading Census Gazetteer from %s", CENSUS_GAZETTEER_URL)
        resp = await client.get(CENSUS_GAZETTEER_URL, follow_redirects=True, timeout=90)
        resp.raise_for_status()
        sha256 = hashlib.sha256(resp.content).hexdigest()

        if not force:
            existing = await session.execute(
                select(RateIngestionRun)
                .where(RateIngestionRun.source == source_name)
                .where(RateIngestionRun.status == "success")
                .where(RateIngestionRun.source_version == sha256)
            )
            if existing.scalar_one_or_none():
                log.info("%s: SHA256 unchanged — skipping", source_name)
                run.status = "skipped"
                run.completed_at = datetime.now(UTC).replace(tzinfo=None)
                run.source_version = sha256
                return

        with _zipfile.ZipFile(_io.BytesIO(resp.content)) as zf:
            txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
            content = zf.read(txt_names[0]).decode("latin-1")

        reader = csv.DictReader(_io.StringIO(content), delimiter="\t")
        processed = inserted = updated = failed = 0
        for row in reader:
            processed += 1
            try:
                z = (row.get("GEOID") or row.get("ZCTA5") or "").strip().zfill(5)
                lat = float((row.get("INTPTLAT") or "").strip())
                lng = float((row.get("INTPTLONG") or "").strip())
                if not z or z == "00000":
                    failed += 1
                    continue
                result = await session.execute(select(ZipCentroid).where(ZipCentroid.zipcode == z))
                existing_row = result.scalar_one_or_none()
                if existing_row is None:
                    session.add(ZipCentroid(zipcode=z, lat=lat, lng=lng))
                    inserted += 1
                else:
                    existing_row.lat = lat
                    existing_row.lng = lng
                    updated += 1
            except Exception as exc:
                log.debug("Centroid row error: %s", exc)
                failed += 1

        run.status = "success"
        run.records_processed = processed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_failed = failed
        run.source_version = sha256
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        log.info(
            "%s: processed=%d inserted=%d updated=%d failed=%d",
            source_name,
            processed,
            inserted,
            updated,
            failed,
        )
    except Exception as exc:
        run.status = "failed"
        run.error_log = str(exc)
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        log.error("%s: FAILED — %s", source_name, exc)
        raise


async def main(force: bool = False) -> None:
    import os

    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./flowshift.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args = {"ssl": False} if db_url.startswith("postgresql") else {}
    engine = create_async_engine(db_url, poolclass=NullPool, connect_args=connect_args)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient(
        headers={"User-Agent": "FlowShift/1.0 (rate-data-ingestion)"},
    ) as client:
        for source_name, url in [
            ("openei_iou_csv", OPENEI_IOU_URL),
            ("openei_noniou_csv", OPENEI_NONIOU_URL),
        ]:
            async with async_session() as session:
                async with session.begin():
                    await _ingest_source(session, source_name, url, client, force)

        async with async_session() as session:
            async with session.begin():
                await _ingest_centroids(session, client, force)

    await engine.dispose()
    log.info("Ingestion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-ingest even if SHA256 unchanged")
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
