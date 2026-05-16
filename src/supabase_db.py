"""
Supabase integration: client database + report history.
Uses direct REST API (no extra dependencies beyond `requests`).
Falls back gracefully when Supabase is not configured.

Secrets required (in .streamlit/secrets.toml or env vars):
  supabase_url        = "https://<project-ref>.supabase.co"
  supabase_service_key = "<service_role key>"
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

import requests


# ── Credentials ───────────────────────────────────────────────────────────────

def _get_creds() -> tuple[str, str]:
    """Return (url, service_role_key). Empty strings if not configured."""
    try:
        import streamlit as st
        url = st.secrets.get("supabase_url", "") or ""
        key = st.secrets.get("supabase_service_key", "") or ""
        return url, key
    except Exception:
        import os
        return (
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_SERVICE_KEY", ""),
        )


def is_configured() -> bool:
    url, key = _get_creds()
    return bool(url and key)


def _headers() -> dict:
    _, key = _get_creds()
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


def _rest(table: str) -> str:
    url, _ = _get_creds()
    return f"{url}/rest/v1/{table}"


# ── Clients ───────────────────────────────────────────────────────────────────

def get_clients() -> dict:
    """
    Load active clients from Supabase.
    Returns a PROFILES-compatible dict (same structure as src/profiles.py).
    Returns empty dict if Supabase is not configured or on any error.
    """
    if not is_configured():
        return {}
    try:
        resp = requests.get(
            _rest("clients"),
            headers=_headers(),
            params={"active": "eq.true", "order": "name.asc"},
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()

        profiles: dict = {}
        for r in rows:
            display = f"{r['name']} ({r['handle']})"
            colors = r.get("colors") or {}
            if isinstance(colors, str):
                colors = json.loads(colors)
            tags = r.get("tags") or []
            profiles[display] = {
                "key":                 r["key"],
                "handle":              r["handle"],
                "name":                r["name"],
                "instagram_id":        r["instagram_id"],
                "facebook_account_id": r["facebook_account_id"],
                "bio":                 r.get("bio", ""),
                "tags":                tags,
                "avatar":              r.get("avatar", "📊"),
                "footer": (
                    r.get("footer")
                    or f"Relatório gerado para <strong>{r['name']}</strong> por Dash Digital."
                ),
                "colors": colors,
            }
        return profiles
    except Exception:
        return {}


def upsert_client(data: dict) -> bool:
    """
    Insert or update a client row.
    `data` must contain at minimum: key, name, handle, instagram_id, facebook_account_id.
    """
    if not is_configured():
        return False
    try:
        resp = requests.post(
            _rest("clients"),
            headers={
                **_headers(),
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=data,
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def deactivate_client(key: str) -> bool:
    """Soft-delete: mark client as inactive (active = false)."""
    if not is_configured():
        return False
    try:
        resp = requests.patch(
            _rest("clients"),
            headers=_headers(),
            params={"key": f"eq.{key}"},
            json={"active": False},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


# ── Report History ─────────────────────────────────────────────────────────────

def save_report_metrics(
    client_key: str,
    date_from: str,
    date_to: str,
    report_type: str,
    data: dict,
) -> bool:
    """
    Save aggregated metrics snapshot to report_history.
    Lightweight: only key totals, not daily arrays.
    """
    if not is_configured():
        return False

    metrics = {
        "total_reach":        data.get("total_reach", 0),
        "total_organic":      data.get("total_organic", 0),
        "total_paid_reach":   data.get("total_paid_reach", 0),
        "total_interactions": data.get("total_interactions", 0),
        "total_likes":        data.get("total_likes", 0),
        "total_comments":     data.get("total_comments", 0),
        "total_saves":        data.get("total_saves", 0),
        "total_shares":       data.get("total_shares", 0),
        "followers_gained":   data.get("followers_gained", 0),
        "followers":          data.get("followers", 0),
        "org_eng_rate":       data.get("org_eng_rate", 0),
        "total_spend":        data.get("total_spend", 0),
        "total_clicks":       data.get("total_clicks", 0),
        "organic_pct":        data.get("organic_pct", 0),
        "paid_pct":           data.get("paid_pct", 0),
        "avg_cpm":            data.get("avg_cpm", 0),
        "avg_cpc":            data.get("avg_cpc", 0),
        "posting_days":       data.get("posting_days", 0),
        "days":               data.get("days", 0),
    }

    payload = {
        "client_key":  client_key,
        "date_from":   date_from,
        "date_to":     date_to,
        "report_type": report_type,
        "metrics":     json.dumps(metrics),
    }

    try:
        resp = requests.post(
            _rest("report_history"),
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def get_previous_metrics(
    client_key: str,
    date_from: str,
    date_to: str,
    report_type: str,
) -> Optional[dict]:
    """
    Fetch metrics for the equivalent previous period.
    Example: current = May 1–31 (31 days) → looks for April 1–30.
    Returns metrics dict or None if not found.
    """
    if not is_configured():
        return None

    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
        n_days    = (dt - df).days + 1
        prev_to   = (df - timedelta(days=1)).isoformat()
        prev_from = (df - timedelta(days=n_days)).isoformat()

        resp = requests.get(
            _rest("report_history"),
            headers=_headers(),
            params={
                "client_key":  f"eq.{client_key}",
                "report_type": f"eq.{report_type}",
                "date_from":   f"eq.{prev_from}",
                "date_to":     f"eq.{prev_to}",
                "order":       "generated_at.desc",
                "limit":       "1",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            raw = rows[0].get("metrics", {})
            if isinstance(raw, str):
                raw = json.loads(raw)
            return raw
    except Exception:
        pass

    return None


def get_history_list(client_key: str, limit: int = 10) -> list:
    """
    Return the last `limit` report history entries for a client.
    Each entry: {date_from, date_to, report_type, generated_at, metrics}.
    """
    if not is_configured():
        return []
    try:
        resp = requests.get(
            _rest("report_history"),
            headers=_headers(),
            params={
                "client_key": f"eq.{client_key}",
                "order":      "generated_at.desc",
                "limit":      str(limit),
                "select":     "date_from,date_to,report_type,generated_at,metrics",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        for r in rows:
            if isinstance(r.get("metrics"), str):
                r["metrics"] = json.loads(r["metrics"])
        return rows
    except Exception:
        return []
