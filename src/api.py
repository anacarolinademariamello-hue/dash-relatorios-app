"""
Fetches Instagram Insights + Meta Ads data directly from the Meta Graph API.
Uses a long-lived User Access Token stored in st.secrets["meta_access_token"].
"""
import json
import requests
from datetime import date, timedelta

GRAPH = "https://graph.facebook.com/v25.0"


# ── Auth ──────────────────────────────────────────────────────────────────────

def _token() -> str:
    try:
        import streamlit as st
        return st.secrets["meta_access_token"]
    except Exception:
        import os
        return os.environ.get("META_ACCESS_TOKEN", "")


def _next_day(d: str) -> str:
    """Return the day after d (ISO string), needed because 'until' is exclusive."""
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def _get(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, timeout=45)
    r.raise_for_status()
    return r.json()


# ── Instagram ─────────────────────────────────────────────────────────────────

def fetch_instagram_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily reach + interactions via Instagram Graph API."""
    ig_id = profile["instagram_id"]
    token = _token()
    # 'until' is exclusive so we add 1 day to include date_to
    until = _next_day(date_to)

    by_date: dict = {}

    # ── Account-level daily reach + follower change ──────────────────────────
    try:
        resp = _get(f"{GRAPH}/{ig_id}/insights", {
            "metric":       "reach",
            "period":       "day",
            "since":        date_from,
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

    # ── Daily follower change ─────────────────────────────────────────────────
    try:
        fc_resp = _get(f"{GRAPH}/{ig_id}/insights", {
            "metric":       "follower_count",
            "period":       "day",
            "since":        date_from,
            "until":        until,
            "access_token": token,
        })
        for v in fc_resp.get("data", [{}])[0].get("values", []):
            d = v["end_time"][:10]
            by_date.setdefault(d, {})["follower_count"] = v["value"]
    except Exception:
        pass  # follower_count opcional

    # ── Media-level engagement (likes, comments, saves, shares) ─────────────
    try:
        media_resp = _get(f"{GRAPH}/{ig_id}/media", {
            "fields":       "id,timestamp,like_count,comments_count,insights.metric(saved,shares)",
            "since":        date_from,
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
        pass  # media insights optional — reach data is enough

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
            "follower_count":     m.get("follower_count", 0),
        })
    return rows


def fetch_instagram_profile(profile: dict) -> dict:
    """Followers / following / media count."""
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
