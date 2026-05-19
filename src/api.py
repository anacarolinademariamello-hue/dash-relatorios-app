"""
Fetches Instagram Insights + Meta Ads data directly from the Meta Graph API.
Uses a long-lived User Access Token stored in st.secrets["meta_access_token"].
"""
import json
import time
import requests
from datetime import date, timedelta

GRAPH_VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"


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


def _get(url: str, params: dict, retries: int = 3) -> dict:
    """
    GET with automatic retry (exponential backoff) and Portuguese error messages.
    Raises immediately (no retry) on auth errors (401/403) and bad requests (400).
    """
    last_exc: Exception = ConnectionError("Falha ao conectar com a API Meta.")

    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=45)

            if r.status_code == 429:
                wait = 10 * (2 ** attempt)
                time.sleep(wait)
                last_exc = ConnectionError(
                    "Limite de requisições da API Meta atingido. Aguarde e tente novamente."
                )
                continue

            r.raise_for_status()
            return r.json()

        except requests.exceptions.Timeout:
            last_exc = TimeoutError(
                "A API Meta não respondeu no tempo limite. "
                "Tente um período menor ou aguarde e tente novamente."
            )

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 401:
                raise PermissionError(
                    "Token Meta inválido ou expirado (401). "
                    "Renove o token em Meta for Developers e atualize os Secrets."
                )
            if code == 403:
                raise PermissionError(
                    "Sem permissão para acessar este recurso (403). "
                    "Verifique se o token tem as permissões instagram_basic e ads_read."
                )
            if code == 400:
                detail = ""
                try:
                    detail = e.response.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                raise ValueError(
                    f"Requisição inválida para a API Meta (400). {detail}"
                )
            if code >= 500:
                last_exc = ConnectionError(
                    f"Servidor da Meta com instabilidade ({code}). Tentando novamente..."
                )
            else:
                raise  # status inesperado — propaga direto

        except requests.exceptions.ConnectionError:
            last_exc = ConnectionError(
                "Sem conexão com a API Meta. Verifique sua internet."
            )

        if attempt < retries - 1:
            time.sleep(2 ** attempt)  # 1s, 2s entre tentativas

    raise last_exc


# ── Instagram ─────────────────────────────────────────────────────────────────

def fetch_instagram_daily(profile: dict, date_from: str, date_to: str) -> list:
    """Daily reach + interactions via Instagram Graph API."""
    ig_id = profile["instagram_id"]
    token = _token()
    until = _next_day(date_to)

    by_date: dict = {}

    # ── Account-level daily reach ────────────────────────────────────────────
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
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass  # reach opcional para períodos antigos

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
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass  # follower_count só disponível nos últimos 30 dias

    # ── Media-level engagement (likes, comments, saves, shares) ─────────────
    # Segue paginação completa — contas ativas podem ter >200 posts no período
    try:
        media_url = f"{GRAPH}/{ig_id}/media"
        media_params = {
            "fields":       "id,timestamp,like_count,comments_count,insights.metric(saved,shares)",
            "since":        date_from,
            "until":        until,
            "limit":        100,
            "access_token": token,
        }
        while media_url:
            media_resp = _get(media_url, media_params)
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
            media_url    = media_resp.get("paging", {}).get("next")
            media_params = {}
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass  # media insights opcionais

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
    """Followers / following / media count + profile picture URL."""
    ig_id = profile["instagram_id"]
    token = _token()

    data = _get(f"{GRAPH}/{ig_id}", {
        "fields":       "followers_count,follows_count,media_count,username",
        "access_token": token,
    })

    picture_url = ""
    try:
        pic_data = _get(f"{GRAPH}/{ig_id}", {
            "fields":       "profile_picture_url",
            "access_token": token,
        })
        picture_url = pic_data.get("profile_picture_url", "")
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass  # foto de perfil opcional

    return {
        "followers_count":     data.get("followers_count", 0),
        "follows_count":       data.get("follows_count", 0),
        "media_count":         data.get("media_count", 0),
        "profile_picture_url": picture_url,
    }


def fetch_instagram_audience(profile: dict) -> dict:
    """
    Lifetime audience breakdown: gender/age and top countries.
    Tries the v17+ format (follower_demographics + breakdown) first,
    then falls back to the legacy audience_gender_age / audience_country metrics.
    """
    ig_id = profile["instagram_id"]
    token = _token()
    result = {"gender_age": {}, "countries": {}}

    # ── Gender + Age ──────────────────────────────────────────────────────────
    try:
        resp = _get(f"{GRAPH}/{ig_id}/insights", {
            "metric":      "follower_demographics",
            "period":      "lifetime",
            "breakdown":   "gender,age",
            "metric_type": "total_value",
            "access_token": token,
        })
        for m in resp.get("data", []):
            if m.get("name") == "follower_demographics":
                tv = m.get("total_value", {})
                for bd in tv.get("breakdowns", []):
                    dims = bd.get("dimension_keys", [])
                    if "gender" in dims and "age" in dims:
                        gi = dims.index("gender")
                        ai = dims.index("age")
                        for res in bd.get("results", []):
                            dv = res.get("dimension_values", [])
                            if len(dv) >= 2:
                                result["gender_age"][f"{dv[gi]}.{dv[ai]}"] = res.get("value", 0)
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass

    if not result["gender_age"]:
        try:
            resp = _get(f"{GRAPH}/{ig_id}/insights", {
                "metric":       "audience_gender_age",
                "period":       "lifetime",
                "access_token": token,
            })
            for m in resp.get("data", []):
                if m.get("name") == "audience_gender_age":
                    vals = m.get("values", [])
                    if vals:
                        result["gender_age"] = vals[-1].get("value", {})
        except (PermissionError, ValueError):
            raise
        except Exception:
            pass

    # ── Countries ─────────────────────────────────────────────────────────────
    try:
        resp = _get(f"{GRAPH}/{ig_id}/insights", {
            "metric":      "follower_demographics",
            "period":      "lifetime",
            "breakdown":   "country",
            "metric_type": "total_value",
            "access_token": token,
        })
        for m in resp.get("data", []):
            if m.get("name") == "follower_demographics":
                tv = m.get("total_value", {})
                for bd in tv.get("breakdowns", []):
                    dims = bd.get("dimension_keys", [])
                    if "country" in dims:
                        ci = dims.index("country")
                        for res in bd.get("results", []):
                            dv = res.get("dimension_values", [])
                            if dv:
                                result["countries"][dv[ci]] = res.get("value", 0)
    except (PermissionError, ValueError):
        raise
    except Exception:
        pass

    if not result["countries"]:
        try:
            resp = _get(f"{GRAPH}/{ig_id}/insights", {
                "metric":       "audience_country",
                "period":       "lifetime",
                "access_token": token,
            })
            for m in resp.get("data", []):
                if m.get("name") == "audience_country":
                    vals = m.get("values", [])
                    if vals:
                        result["countries"] = vals[-1].get("value", {})
        except (PermissionError, ValueError):
            raise
        except Exception:
            pass

    return result


def fetch_instagram_top_posts(profile: dict, date_from: str, date_to: str) -> list:
    """
    Top posts with media_type and full engagement metrics.
    Fetches up to 200 posts (2 pages of 100) and stores the full ISO timestamp
    so the processor can compute best-hour-to-post analysis.
    """
    ig_id = profile["instagram_id"]
    token = _token()
    until = _next_day(date_to)
    all_media = []

    try:
        params = {
            "fields":       "id,timestamp,media_type,media_product_type,permalink,"
                            "like_count,comments_count,insights.metric(saved,shares,reach,impressions)",
            "since":        date_from,
            "until":        until,
            "limit":        100,
            "access_token": token,
        }
        resp = _get(f"{GRAPH}/{ig_id}/media", params)
        all_media = list(resp.get("data", []))

        # Paginação completa — segue até não haver mais páginas
        next_url = resp.get("paging", {}).get("next", "")
        while next_url:
            try:
                resp_next = _get(next_url, {})
                all_media.extend(resp_next.get("data", []))
                next_url = resp_next.get("paging", {}).get("next", "")
            except Exception:
                break  # página extra falhou — usa o que já tem

    except (PermissionError, ValueError):
        raise
    except Exception:
        pass

    posts = []
    for m in all_media:
        post = {
            "id":                m.get("id", ""),
            "timestamp":         m.get("timestamp", ""),        # ISO completo para análise de horário
            "date":              (m.get("timestamp") or "")[:10],
            "media_type":        m.get("media_type", "IMAGE"),
            "media_product_type": m.get("media_product_type", ""),
            "permalink":         m.get("permalink", ""),
            "likes":             int(m.get("like_count") or 0),
            "comments":          int(m.get("comments_count") or 0),
            "saves":             0,
            "shares":            0,
            "reach":             0,
            "impressions":       0,
        }
        for ins in (m.get("insights") or {}).get("data", []):
            val  = int((ins.get("values") or [{}])[0].get("value") or 0)
            name = ins.get("name", "")
            if name == "saved":
                post["saves"] = val
            elif name == "shares":
                post["shares"] = val
            elif name == "reach":
                post["reach"] = val
            elif name == "impressions":
                post["impressions"] = val
        post["total_interactions"] = (
            post["likes"] + post["comments"] + post["saves"] + post["shares"]
        )
        posts.append(post)

    return posts


# ── Meta Ads ──────────────────────────────────────────────────────────────────

def fetch_meta_ads_daily(profile: dict, date_from: str, date_to: str) -> list:
    """
    Daily Meta Ads data by campaign via Marketing API.
    Follows pagination to garantee all campaigns and all days are included.
    """
    act_id = profile["facebook_account_id"]
    token  = _token()

    url = f"{GRAPH}/act_{act_id}/insights"
    params = {
        "fields":         "campaign_name,objective,spend,impressions,reach,clicks,cpm,cpc,ctr",
        "level":          "campaign",
        "time_range":     json.dumps({"since": date_from, "until": date_to}),
        "time_increment": 1,
        "limit":          500,   # máximo por página — evita truncamento
        "access_token":   token,
    }

    rows = []
    while url:
        resp  = _get(url, params)
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
        # Segue paginação — next já contém todos os parâmetros na URL
        url    = resp.get("paging", {}).get("next")
        params = {}

    return rows
