#!/usr/bin/env python3
"""
Ingest NREL Utility Rate Database (URDB) bulk residential rates.

Downloads usurdb.json.gz from OpenEI, filters to active Residential tariffs,
upserts into the urdb_rate table, and writes a rate_ingestion_run audit row.

Idempotent: the gzip file's SHA-256 hash is stored as source_version; if the
remote file is unchanged since the last successful run, the download is skipped.

Usage:
    python scripts/ingest_urdb.py [--force]

    --force     Re-ingest even if the remote file hash matches the last run.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import io
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models import RateIngestionRun, UrdbRate

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

URDB_URL = "https://openei.org/apps/USURDB/download/usurdb.json.gz"
SOURCE_KEY = "openei_urdb_residential"
BATCH_SIZE = 500


async def _last_source_version(session, source: str) -> str | None:
    result = await session.execute(
        select(RateIngestionRun.source_version)
        .where(
            RateIngestionRun.source == source,
            RateIngestionRun.status == "success",
        )
        .order_by(RateIngestionRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _write_run(
    session,
    source: str,
    started_at: datetime,
    status: str,
    source_version: str | None = None,
    processed: int = 0,
    inserted: int = 0,
    updated: int = 0,
    failed: int = 0,
    error_log: str | None = None,
) -> None:
    run = RateIngestionRun(
        source=source,
        started_at=started_at,
        completed_at=datetime.now(UTC).replace(tzinfo=None),
        status=status,
        source_version=source_version,
        records_processed=processed,
        records_inserted=inserted,
        records_updated=updated,
        records_failed=failed,
        error_log=error_log,
    )
    session.add(run)
    await session.commit()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_date(ts: int | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return None


def _is_active(record: dict) -> bool:
    end_ts = record.get("enddate") or 0
    if end_ts <= 0:
        return True
    end_dt = datetime.fromtimestamp(end_ts, tz=UTC)
    return end_dt > datetime.now(UTC)


def _urdb_last_modified(record: dict) -> datetime | None:
    ts = record.get("startdate") or 0
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None)
    except (OSError, ValueError):
        return None


async def _upsert_batch(session, batch: list[dict]) -> tuple[int, int, int]:
    inserted = updated = failed = 0
    for record in batch:
        label = str(record.get("label", "")).strip()
        if not label:
            failed += 1
            continue
        try:
            existing = await session.get(UrdbRate, label)
            eia_raw = record.get("eia") or record.get("eiaid")
            eia_id = int(eia_raw) if eia_raw else None
            is_active = _is_active(record)

            if existing is None:
                session.add(
                    UrdbRate(
                        urdb_label=label,
                        eia_id=eia_id,
                        name=record.get("name"),
                        sector=record.get("sector"),
                        effective_date=_parse_date(record.get("startdate")),
                        end_date=_parse_date(record.get("enddate") or 0),
                        is_active=is_active,
                        raw_json=record,
                        urdb_last_modified=_urdb_last_modified(record),
                    )
                )
                inserted += 1
            else:
                existing.eia_id = eia_id
                existing.name = record.get("name")
                existing.sector = record.get("sector")
                existing.effective_date = _parse_date(record.get("startdate"))
                existing.end_date = _parse_date(record.get("enddate") or 0)
                existing.is_active = is_active
                existing.raw_json = record
                existing.urdb_last_modified = _urdb_last_modified(record)
                updated += 1
        except Exception as exc:
            log.warning("Failed to upsert label=%s: %s", label, exc)
            failed += 1

    await session.commit()
    return inserted, updated, failed


async def ingest(force: bool = False) -> None:
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./flowshift.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args = {"ssl": False} if database_url.startswith("postgresql") else {}
    engine = create_async_engine(database_url, connect_args=connect_args)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    started_at = datetime.now(UTC).replace(tzinfo=None)

    async with factory() as session:
        log.info("Downloading URDB bulk file from %s …", URDB_URL)
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.get(URDB_URL, follow_redirects=True)
                resp.raise_for_status()
                raw_bytes = resp.content
        except Exception as exc:
            log.error("Download failed: %s", exc)
            await _write_run(
                session,
                SOURCE_KEY,
                started_at,
                "failed",
                error_log=str(exc),
            )
            return

        file_hash = _sha256(raw_bytes)
        log.info("Downloaded %d bytes, SHA-256: %s", len(raw_bytes), file_hash)

        if not force:
            last_version = await _last_source_version(session, SOURCE_KEY)
            if last_version == file_hash:
                log.info("File unchanged since last successful run — skipping.")
                await _write_run(
                    session,
                    SOURCE_KEY,
                    started_at,
                    "skipped",
                    source_version=file_hash,
                )
                return

        # Decompress and parse
        try:
            with gzip.open(io.BytesIO(raw_bytes)) as gz:
                records = json.loads(gz.read())
        except Exception as exc:
            log.error("Failed to decompress/parse: %s", exc)
            await _write_run(
                session,
                SOURCE_KEY,
                started_at,
                "failed",
                source_version=file_hash,
                error_log=str(exc),
            )
            return

        if isinstance(records, dict):
            # Some OpenEI responses wrap the array in an "items" key
            records = records.get("items", records.get("rates", []))

        log.info("Total records in file: %d", len(records))

        # Filter to active Residential tariffs with energy rate data
        residential = [
            r
            for r in records
            if (r.get("sector") or "").lower().startswith("residential")
            and r.get("energyratestructure")
        ]
        log.info("Residential records with energy rates: %d", len(residential))

        total_processed = inserted = updated = failed = 0

        for i in range(0, len(residential), BATCH_SIZE):
            batch = residential[i : i + BATCH_SIZE]
            bi, bu, bf = await _upsert_batch(session, batch)
            inserted += bi
            updated += bu
            failed += bf
            total_processed += len(batch)
            log.info(
                "  Batch %d/%d — inserted=%d updated=%d failed=%d",
                i // BATCH_SIZE + 1,
                (len(residential) + BATCH_SIZE - 1) // BATCH_SIZE,
                bi,
                bu,
                bf,
            )

        log.info(
            "Done: processed=%d inserted=%d updated=%d failed=%d",
            total_processed,
            inserted,
            updated,
            failed,
        )
        await _write_run(
            session,
            SOURCE_KEY,
            started_at,
            "success",
            source_version=file_hash,
            processed=total_processed,
            inserted=inserted,
            updated=updated,
            failed=failed,
        )

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest URDB residential rates.")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if file hash matches.")
    args = parser.parse_args()
    asyncio.run(ingest(force=args.force))
