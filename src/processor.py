from datetime import date, timedelta
from collections import defaultdict

# Country code → Portuguese name
COUNTRY_NAMES = {
    "BR": "Brasil", "US": "EUA", "PT": "Portugal", "AR": "Argentina",
    "MX": "México", "CO": "Colômbia", "CL": "Chile", "PE": "Peru",
    "ES": "Espanha", "GB": "Reino Unido", "FR": "França", "DE": "Alemanha",
    "IT": "Itália", "JP": "Japão", "CA": "Canadá", "AU": "Austrália",
    "UY": "Uruguai", "PY": "Paraguai", "BO": "Bolívia", "EC": "Equador",
    "VE": "Venezuela", "CR": "Costa Rica", "GT": "Guatemala", "PA": "Panamá",
    "DO": "Rep. Dominicana", "CU": "Cuba", "HN": "Honduras", "NI": "Nicarágua",
    "SV": "El Salvador", "AO": "Angola", "MZ": "Moçambique",
}


def _date_range(date_from: str, date_to: str):
    start = date.fromisoformat(date_from)
    end   = date.fromisoformat(date_to)
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _fmt_label(d: date) -> str:
    return d.strftime("%d/%m")


def _media_format(post: dict) -> str:
    """Map API media_type / media_product_type to friendly Portuguese name."""
    if post.get("media_product_type") == "REELS":
        return "Reel"
    mt = post.get("media_type", "IMAGE")
    if mt == "CAROUSEL_ALBUM":
        return "Carrossel"
    if mt == "VIDEO":
        return "Vídeo"
    return "Foto"


def _process_audience(audience_data: dict) -> dict:
    """Process raw gender_age + countries into clean display-ready data."""
    gender_age   = audience_data.get("gender_age", {})
    countries_raw = audience_data.get("countries", {})

    # ── Gender + Age aggregation ──────────────────────────────────────────────
    gender_totals = {"M": 0, "F": 0, "U": 0}
    age_totals    = {}

    for key, count in gender_age.items():
        parts = key.split(".")
        if len(parts) == 2:
            g, age = parts
            gender_totals[g] = gender_totals.get(g, 0) + int(count)
            age_totals[age]  = age_totals.get(age, 0)  + int(count)

    total_ga = sum(gender_totals.values())
    gender_pct = {
        k: round(v / total_ga * 100, 1) if total_ga else 0
        for k, v in gender_totals.items()
    }

    # Age brackets in order
    age_order  = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    age_labels = [a for a in age_order if a in age_totals]
    age_values = [age_totals[a] for a in age_labels]
    total_age  = sum(age_values) or 1
    age_pcts   = [round(v / total_age * 100, 1) for v in age_values]

    # Top countries (max 8)
    sorted_countries = sorted(countries_raw.items(), key=lambda x: -x[1])[:8]
    country_labels   = [COUNTRY_NAMES.get(c[0], c[0]) for c in sorted_countries]
    country_values   = [c[1] for c in sorted_countries]
    total_countries  = sum(country_values) or 1
    country_pcts     = [round(v / total_countries * 100, 1) for v in country_values]

    # Dominant age bracket
    dominant_age = age_labels[age_pcts.index(max(age_pcts))] if age_pcts else "—"

    return {
        "gender_totals":  gender_totals,
        "gender_pct":     gender_pct,
        "age_labels":     age_labels,
        "age_values":     age_values,
        "age_pcts":       age_pcts,
        "country_labels": country_labels,
        "country_values": country_values,
        "country_pcts":   country_pcts,
        "dominant_age":   dominant_age,
        "has_data":       total_ga > 0,
    }


def _process_top_posts(top_posts: list, followers: int) -> dict:
    """Process top posts into content-type analysis and ranking."""
    if not top_posts:
        return {"formats": [], "top_posts": [], "best_format": None, "has_data": False}

    # Attach friendly format name to each post
    for post in top_posts:
        post["format"] = _media_format(post)

    # Group by format
    by_format: dict = {}
    for post in top_posts:
        fmt = post["format"]
        if fmt not in by_format:
            by_format[fmt] = {"count": 0, "total_reach": 0, "total_interactions": 0, "total_saves": 0}
        by_format[fmt]["count"]              += 1
        by_format[fmt]["total_reach"]        += post.get("reach", 0)
        by_format[fmt]["total_interactions"] += post.get("total_interactions", 0)
        by_format[fmt]["total_saves"]        += post.get("saves", 0)

    formats = []
    for fmt, stats in by_format.items():
        cnt      = stats["count"]
        avg_r    = round(stats["total_reach"] / cnt)        if cnt else 0
        avg_int  = round(stats["total_interactions"] / cnt) if cnt else 0
        avg_eng  = round(avg_int / avg_r * 100, 2)          if avg_r else 0
        avg_save = round(stats["total_saves"] / cnt)        if cnt else 0
        formats.append({
            "name":              fmt,
            "count":             cnt,
            "avg_reach":         avg_r,
            "avg_interactions":  avg_int,
            "avg_eng_rate":      avg_eng,
            "avg_saves":         avg_save,
        })
    formats.sort(key=lambda x: -x["avg_interactions"])

    # Best format by avg interactions
    best_format = formats[0]["name"] if formats else None

    # Top 10 posts by total_interactions
    top10 = sorted(top_posts, key=lambda x: -x.get("total_interactions", 0))[:10]

    return {
        "formats":     formats,
        "top_posts":   top10,
        "best_format": best_format,
        "has_data":    len(top_posts) > 0,
    }


def process(ig_rows: list, ads_rows: list, profile_info: dict,
            audience_data: dict, top_posts: list,
            date_from: str, date_to: str) -> dict:
    """
    Combine Instagram + Meta Ads raw rows into clean arrays ready for the HTML generator.
    """
    days     = list(_date_range(date_from, date_to))
    labels   = [_fmt_label(d) for d in days]
    day_keys = [d.isoformat() for d in days]

    # ── Instagram daily ──────────────────────────────────────────────
    ig_by_date = {}
    for row in ig_rows:
        k = row.get("date", "")[:10]
        if k:
            ig_by_date[k] = row

    daily_reach            = []
    daily_likes            = []
    daily_comments         = []
    daily_saves            = []
    daily_shares           = []
    daily_interactions     = []
    daily_follower_change  = []

    for k in day_keys:
        r = ig_by_date.get(k, {})
        daily_reach.append(int(r.get("reach") or 0))
        daily_likes.append(int(r.get("likes") or 0))
        daily_comments.append(int(r.get("comments") or 0))
        daily_saves.append(int(r.get("saves") or 0))
        daily_shares.append(int(r.get("shares") or 0))
        daily_interactions.append(int(r.get("total_interactions") or 0))
        daily_follower_change.append(int(r.get("follower_count") or 0))

    # ── Meta Ads daily ───────────────────────────────────────────────
    ads_by_date = defaultdict(list)
    for row in ads_rows:
        k = row.get("date", "")[:10]
        if k:
            ads_by_date[k].append(row)

    # Campaign aggregates
    camp_totals = defaultdict(lambda: {
        "objective": "", "spend": 0.0, "impressions": 0,
        "reach": 0, "clicks": 0,
    })
    for row in ads_rows:
        cn = row.get("campaign_name") or "Sem nome"
        ct = camp_totals[cn]
        ct["objective"]   = row.get("objective") or ct["objective"]
        ct["spend"]       += float(row.get("spend") or 0)
        ct["impressions"] += int(row.get("impressions") or 0)
        ct["reach"]       += int(row.get("reach") or 0)
        ct["clicks"]      += int(row.get("clicks") or 0)

    campaigns = []
    for name, t in sorted(camp_totals.items(), key=lambda x: -x[1]["spend"]):
        sp  = t["spend"]
        im  = t["impressions"]
        cl  = t["clicks"]
        re  = t["reach"]
        cpm = round(sp / im * 1000, 2) if im else 0
        cpc = round(sp / cl, 2)        if cl else 0
        ctr = round(cl / im * 100, 2)  if im else 0
        # Status heuristic
        if ctr >= 4.0:
            status = "best"
        elif ctr >= 2.5:
            status = "ok"
        elif sp < 30:
            status = "ended"
        else:
            status = "warning"
        campaigns.append({
            "name": name, "objective": t["objective"],
            "spend": sp, "impressions": im, "reach": re,
            "clicks": cl, "cpm": cpm, "cpc": cpc, "ctr": ctr,
            "status": status,
        })

    # Daily paid reach + spend
    daily_paid_reach = []
    daily_spend      = []
    for k in day_keys:
        rows_day = ads_by_date.get(k, [])
        daily_paid_reach.append(sum(int(r.get("reach") or 0)   for r in rows_day))
        daily_spend.append(round(sum(float(r.get("spend") or 0) for r in rows_day), 2))

    # Organic reach = total reach - paid (floor 0)
    daily_organic_reach = [max(0, daily_reach[i] - daily_paid_reach[i]) for i in range(len(days))]

    # ── Totals ───────────────────────────────────────────────────────
    total_reach        = sum(daily_reach)
    total_organic      = sum(daily_organic_reach)
    total_paid_reach   = sum(daily_paid_reach)
    total_interactions = sum(daily_interactions)
    total_likes        = sum(daily_likes)
    total_comments     = sum(daily_comments)
    total_saves        = sum(daily_saves)
    total_shares       = sum(daily_shares)
    total_spend        = round(sum(daily_spend), 2)
    total_impressions  = sum(c["impressions"] for c in campaigns)
    total_clicks       = sum(c["clicks"]      for c in campaigns)

    organic_pct  = round(total_organic / total_reach * 100, 1)   if total_reach else 0
    paid_pct     = round(100 - organic_pct, 1)
    org_eng_rate = round(total_interactions / total_organic * 100, 2) if total_organic else 0
    avg_cpm      = round(total_spend / total_impressions * 1000, 2)   if total_impressions else 0
    avg_cpc      = round(total_spend / total_clicks, 2)               if total_clicks else 0

    followers   = int(profile_info.get("followers_count") or 0)
    following   = int(profile_info.get("follows_count") or 0)
    media       = int(profile_info.get("media_count") or 0)
    picture_url = profile_info.get("profile_picture_url", "")

    # Followers gained in period
    followers_gained = sum(daily_follower_change)

    # Paid followers estimate from traffic/profile campaigns
    traffic_clicks = sum(
        c["clicks"] for c in campaigns
        if any(w in c["name"].lower() for w in ("tráfego", "perfil", "traffic", "seguidores"))
    )
    followers_paid_est = max(0, int(traffic_clicks * 0.28))

    if followers_gained > 0:
        followers_organic_est = max(0, followers_gained - followers_paid_est)
    else:
        followers_gained      = followers_paid_est
        followers_organic_est = 0

    cost_per_follower = round(total_spend / max(1, followers_paid_est), 2) if total_spend else 0
    new_followers_est = followers_gained

    # Posting frequency
    posting_days = sum(1 for k in day_keys if any(
        (p.get("date") or "")[:10] == k for p in top_posts
    ))

    period_label = f"{labels[0]} – {labels[-1]} {days[0].year}"

    # ── Audience + Content Analysis ──────────────────────────────────
    audience_analysis  = _process_audience(audience_data)
    content_analysis   = _process_top_posts(top_posts, followers)

    return {
        "labels": labels,
        "days": len(days),
        "period_label": period_label,
        "date_from": date_from,
        "date_to": date_to,
        # Instagram profile
        "followers": followers,
        "following": following,
        "media": media,
        "picture_url": picture_url,
        # Followers
        "followers_gained":       followers_gained,
        "followers_organic_est":  followers_organic_est,
        "followers_paid_est":     followers_paid_est,
        "new_followers_est":      new_followers_est,
        "cost_per_follower":      cost_per_follower,
        # Reach
        "total_reach":      total_reach,
        "total_organic":    total_organic,
        "total_paid_reach": total_paid_reach,
        "organic_pct":      organic_pct,
        "paid_pct":         paid_pct,
        # Engagement
        "total_interactions": total_interactions,
        "total_likes":        total_likes,
        "total_comments":     total_comments,
        "total_saves":        total_saves,
        "total_shares":       total_shares,
        "org_eng_rate":       org_eng_rate,
        # Paid
        "total_spend":      total_spend,
        "total_impressions": total_impressions,
        "total_clicks":     total_clicks,
        "avg_cpm":          avg_cpm,
        "avg_cpc":          avg_cpc,
        "campaigns":        campaigns,
        # Daily arrays
        "daily_reach":           daily_reach,
        "daily_organic_reach":   daily_organic_reach,
        "daily_paid_reach":      daily_paid_reach,
        "daily_likes":           daily_likes,
        "daily_comments":        daily_comments,
        "daily_saves":           daily_saves,
        "daily_shares":          daily_shares,
        "daily_interactions":    daily_interactions,
        "daily_spend":           daily_spend,
        "daily_follower_change": daily_follower_change,
        # Content analysis
        "posting_days":      posting_days,
        "audience":          audience_analysis,
        "content":           content_analysis,
    }
