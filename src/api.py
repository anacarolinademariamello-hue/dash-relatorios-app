"""
Fetches Instagram Insights + Meta Ads data directly from the Meta Graph API.
No third-party connector needed — uses the long-lived user access token.
Token expires in ~60 days; regenerate via the OAuth flow in developers.facebook.com.
"""
import json
import requests
from datetime import datetime

GRAPH = "https://graph.facebook.com/v21.0"


# ── Auth ──────────────────────────────────────────────────────────────────────

def _token() -> str:
    try:
        import streamlit as st
        return st.secrets["meta_access_token"]
    except Exception:
        import os
        return os.environ.get("META_ACCESS_TOKEN", "")


def _ts(d: str) -> int:
    """ISO date string (YYYY-MM-DD) → Unix timestamp (midnight UTC)."""
    return int(datetime.strptime(d, "%Y-%m-%d").timestamp())


def _get(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, timeout=45)
    r.raise_for_status()
    return r.json()


# ── Instagram ─────────────────────────────────────────────────────────────────

def fetch_instagram_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily reach + interactions for the period via Instagram Graph API."""
    ig_id = profile["instagram_id"]
    token = _token()
    since = _ts(date_from)
    until = _ts(date_to) + 86400  # include the full last day

    by_date: dict = {}

    # ── Account-level daily reach & impressions ──────────────────────────────
    try:
        resp = _get(f"{GRAPH}/{ig_id}/insights", {
            "metric":       "reach,impressions",
            "period":       "day",
            "since":        since,
            "until":        until,
            "access_token": token,
        })
        for metric_obj in resp.get("data", []):
            name = metric_obj["name"]
            for v in metric_obj.get("values", []):
                d = v["end_time"][:10]
                by_date.setdefault(d, {})[name] = v["value"]
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar insights do Instagram: {e}")

    # ── Media-level engagement (likes, comments, saves, shares) ─────────────
    try:
        media_resp = _get(f"{GRAPH}/{ig_id}/media", {
            "fields":       "id,timestamp,like_count,comments_count,insights.metric(saved,shares)",
            "since":        since,
            "until":        until,
            "limit":        200,
            "access_token": token,
        })
        for media in media_resp.get("data", []):
            d = (media.get("timestamp") or "")[:10]
            if not d:
                continue
            by_date.setdefault(d, {})
            by_date[d]["likes"]    = by_date[d].get("likes", 0)    + int(media.get("like_count") or 0)
            by_date[d]["comments"] = by_date[d].get("comments", 0) + int(media.get("comments_count") or 0)
            for ins in (media.get("insights") or {}).get("data", []):
                val = int((ins.get("values") or [{}])[0].get("value") or 0)
                if ins["name"] == "saved":
                    by_date[d]["saves"]  = by_date[d].get("saves", 0)  + val
                elif ins["name"] == "shares":
                    by_date[d]["shares"] = by_date[d].get("shares", 0) + val
    except Exception:
        pass  # media insights are optional — reach data is enough to proceed

    # ── Build rows ───────────────────────────────────────────────────────────
    rows = []
    for d, m in sorted(by_date.items()):
        likes    = m.get("likes", 0)
        comments = m.get("comments", 0)
        saves    = m.get("saves", 0)
        shares   = m.get("shares", 0)
        rows.append({
            "date":               d,
            "reach":              m.get("reach", 0),
            "likes":              likes,
            "comments":           comments,
            "saves":              saves,
            "shares":             shares,
            "total_interactions": likes + comments + saves + shares,
        })
    return rows


def fetch_instagram_profile(profile: dict) -> dict:
    """Followers / following / media count from the Instagram profile."""
    ig_id = profile["instagram_id"]
    token = _token()
    data = _get(f"{GRAPH}/{ig_id}", {
        "fields":       "followers_count,follows_count,media_count,username",
        "access_token": token,
    })
    return {
        "followers_count": data.get("followers_count", 0),
        "follows_count":   data.get("follows_count", 0),
        "media_count":     data.get("media_count", 0),
    }


# ── Meta Ads ──────────────────────────────────────────────────────────────────

def fetch_meta_ads_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily Meta Ads data by campaign via Marketing API."""
    act_id = profile["facebook_account_id"]
    token  = _token()

    resp = _get(f"{GRAPH}/act_{act_id}/insights", {
        "fields":         "campaign_name,objective,spend,impressions,reach,clicks,cpm,cpc,ctr",
        "level":          "campaign",
        "time_range":     json.dumps({"since": date_from, "until": date_to}),
        "time_increment": 1,
        "access_token":   token,
    })

    rows = []
    for item in resp.get("data", []):
        rows.append({
            "date":          item.get("date_start", ""),
            "campaign_name": item.get("campaign_name", ""),
            "objective":     item.get("objective", ""),
            "spend":         item.get("spend", 0),
            "impressions":   item.get("impressions", 0),
            "reach":         item.get("reach", 0),
            "clicks":        item.get("clicks", 0),
            "cpm":           item.get("cpm", 0),
            "cpc":           item.get("cpc", 0),
            "ctr":           item.get("ctr", 0),
        })
    return rows
