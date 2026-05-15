import requests
from datetime import date

WINDSOR_BASE = "https://connectors.windsor.ai/all"


def _api_key() -> str:
    try:
        import streamlit as st
        return st.secrets["windsor_api_key"]
    except Exception:
        import os
        return os.environ.get("WINDSOR_API_KEY", "")


def _get(params: dict) -> list:
    r = requests.get(WINDSOR_BASE, params=params, timeout=45)
    r.raise_for_status()
    body = r.json()
    return body.get("result", body.get("data", []))


def fetch_instagram_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily Instagram reach + interactions for the period."""
    return _get({
        "api_key": _api_key(),
        "connector": "instagram",
        "date_from": date_from,
        "date_to": date_to,
        "fields": "date,reach,likes,comments,shares,saves,total_interactions",
        "account_id": profile["instagram_id"],
    })


def fetch_instagram_profile(profile: dict) -> dict:
    """Latest followers / following / media count."""
    rows = _get({
        "api_key": _api_key(),
        "connector": "instagram",
        "date_preset": "last_1dT",
        "fields": "date,followers_count,follows_count,media_count",
        "account_id": profile["instagram_id"],
    })
    # The profile row has nulls for daily metrics — find the one with followers_count
    for row in reversed(rows):
        if row.get("followers_count"):
            return row
    return rows[-1] if rows else {}


def fetch_meta_ads_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily Meta Ads data by campaign."""
    return _get({
        "api_key": _api_key(),
        "connector": "facebook",
        "date_from": date_from,
        "date_to": date_to,
        "fields": "date,campaign_name,objective,spend,impressions,reach,clicks,cpm,cpc,ctr",
        "account_id": profile["facebook_account_id"],
    })
