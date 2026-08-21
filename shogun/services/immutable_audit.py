"""HMAC-chained audit log, append-only through the application service.

The separate SQLite database reduces accidental coupling to operational-log
maintenance. Each record is hash-chained to the previous one so verification
can reveal mismatches in the covered fields. This is tamper-evident application
behaviour, not immutable storage, and it does not prove that every event was
captured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# HMAC key — in production, load from env/secrets manager
_HMAC_KEY = b"shogun-audit-integrity-key-v1"

_AUDIT_DB_PATH: Path | None = None
_initialized = False


def _get_audit_db_path() -> Path:
    global _AUDIT_DB_PATH
    if _AUDIT_DB_PATH is None:
        from shogun.config import PROJECT_ROOT
        data_dir = PROJECT_ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        _AUDIT_DB_PATH = data_dir / "audit_immutable.db"
    return _AUDIT_DB_PATH


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the separate append-only audit database."""
    db_path = _get_audit_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_table():
    """Create the audit table if it doesn't exist."""
    global _initialized
    if _initialized:
        return
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_chain (
                seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                action TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT 'success',
                user_id TEXT,
                agent_id TEXT,
                session_id TEXT,
                trace_id TEXT,
                model_used TEXT,
                provider_used TEXT,
                tool_name TEXT,
                policy_ref TEXT,
                policy_decision TEXT,
                policy_reason TEXT,
                risk_score TEXT DEFAULT 'low',
                detail TEXT DEFAULT '{}',
                memory_ids TEXT DEFAULT '[]',
                prev_hash TEXT NOT NULL,
                record_hash TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_chain(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_chain(event_category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_chain(trace_id)"
        )
        conn.commit()
        _initialized = True
    finally:
        conn.close()


def _compute_hash(
    event_id: str,
    timestamp: str,
    category: str,
    event_type: str,
    action: str,
    result: str,
    prev_hash: str,
) -> str:
    """Compute HMAC-SHA256 hash for a record in the chain."""
    message = f"{event_id}|{timestamp}|{category}|{event_type}|{action}|{result}|{prev_hash}"
    return hmac.new(_HMAC_KEY, message.encode(), hashlib.sha256).hexdigest()


def _get_last_hash(conn: sqlite3.Connection) -> str:
    """Get the hash of the last record in the chain, or genesis hash."""
    cursor = conn.execute(
        "SELECT record_hash FROM audit_chain ORDER BY seq_id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return row[0] if row else "GENESIS"


def append(
    *,
    event_id: str,
    event_category: str,
    event_type: str,
    action: str,
    result: str = "success",
    severity: str = "info",
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
    model_used: str | None = None,
    provider_used: str | None = None,
    tool_name: str | None = None,
    policy_ref: str | None = None,
    policy_decision: str | None = None,
    policy_reason: str | None = None,
    risk_score: str = "low",
    detail: dict | None = None,
    memory_ids: list | None = None,
) -> None:
    """Append an event to the HMAC-chained audit log.

    This module exposes no update or delete operation. A process or database
    administrator with file access can still alter the underlying SQLite file.
    """
    _ensure_table()
    timestamp = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        prev_hash = _get_last_hash(conn)
        record_hash = _compute_hash(
            event_id, timestamp, event_category, event_type,
            action, result, prev_hash,
        )

        conn.execute(
            """INSERT INTO audit_chain (
                event_id, timestamp, event_category, event_type, severity,
                action, result, user_id, agent_id, session_id, trace_id,
                model_used, provider_used, tool_name,
                policy_ref, policy_decision, policy_reason, risk_score,
                detail, memory_ids, prev_hash, record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, timestamp, event_category, event_type, severity,
                action, result, user_id, str(agent_id) if agent_id else None,
                str(session_id) if session_id else None, trace_id,
                model_used, provider_used, tool_name,
                policy_ref, policy_decision, policy_reason, risk_score,
                json.dumps(detail or {}), json.dumps(memory_ids or []),
                prev_hash, record_hash,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.error("Append-only audit write failed: %s", e)
    finally:
        conn.close()


def verify_chain() -> dict:
    """Verify the integrity of the entire audit chain.

    Returns verification result with total records, verified count,
    and the position where the chain breaks (if any).
    """
    _ensure_table()
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT seq_id, event_id, timestamp, event_category, event_type, "
            "action, result, prev_hash, record_hash "
            "FROM audit_chain ORDER BY seq_id ASC"
        )
        rows = cursor.fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total_records": 0,
                "verified_records": 0,
                "chain_intact": True,
                "message": "Audit chain is empty.",
            }

        expected_prev = "GENESIS"
        verified = 0

        for row in rows:
            seq_id, event_id, timestamp, category, event_type, action, result, prev_hash, record_hash = row

            # Check prev_hash chain
            if prev_hash != expected_prev:
                return {
                    "total_records": total,
                    "verified_records": verified,
                    "broken_at": seq_id,
                    "chain_intact": False,
                    "message": f"Chain broken at record seq_id={seq_id}: "
                               f"expected prev_hash={expected_prev[:16]}..., "
                               f"got {prev_hash[:16]}...",
                }

            # Verify HMAC
            computed = _compute_hash(
                event_id, timestamp, category, event_type, action, result, prev_hash
            )
            if computed != record_hash:
                return {
                    "total_records": total,
                    "verified_records": verified,
                    "broken_at": seq_id,
                    "chain_intact": False,
                    "message": f"HMAC mismatch at record seq_id={seq_id}: "
                               f"record may have been tampered with.",
                }

            expected_prev = record_hash
            verified += 1

        return {
            "total_records": total,
            "verified_records": verified,
            "chain_intact": True,
            "last_verified_at": datetime.now(timezone.utc).isoformat(),
            "message": (
                f"All {total} available audit records matched the HMAC chain. "
                "This check does not prove record completeness."
            ),
        }
    finally:
        conn.close()


def export_records(
    *,
    category: str | None = None,
    trace_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10000,
) -> list[dict]:
    """Export audit records for compliance review."""
    _ensure_table()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM audit_chain WHERE 1=1"
        params: list = []

        if category:
            query += " AND event_category = ?"
            params.append(category)
        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)
        if date_from:
            query += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            query += " AND timestamp <= ?"
            params.append(date_to)

        query += " ORDER BY seq_id ASC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
