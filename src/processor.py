from datetime import date, timedelta
from collections import defaultdict


def _date_range(date_from: str, date_to: str):
    start = date.fromisoformat(date_from)
    end   = date.fromisoformat(date_to)
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _fmt_label(d: date) -> str:
    return d.strftime("%d/%m")


def process(ig_rows: list, ads_rows: list, profile_info: dict,
            date_from: str, date_to: str) -> dict:
    """
    Combine Instagram + Meta Ads raw rows into clean arrays ready for the HTML generator.
    """
    days = list(_date_range(date_from, date_to))
    labels = [_fmt_label(d) for d in days]
    day_keys = [d.isoformat() for d in days]

    # ── Instagram daily ──────────────────────────────────────────────
    ig_by_date = {}
    for row in ig_rows:
        k = row.get("date", "")[:10]
        if k:
            ig_by_date[k] = row

    daily_reach = []
    daily_likes = []
    daily_comments = []
    daily_saves = []
    daily_shares = []
    daily_interactions = []
    daily_follower_change = []

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
        ct["objective"] = row.get("objective") or ct["objective"]
        ct["spend"]      += float(row.get("spend") or 0)
        ct["impressions"] += int(row.get("impressions") or 0)
        ct["reach"]       += int(row.get("reach") or 0)
        ct["clicks"]      += int(row.get("clicks") or 0)

    campaigns = []
    for name, t in sorted(camp_totals.items(), key=lambda x: -x[1]["spend"]):
        sp = t["spend"]
        im = t["impressions"]
        cl = t["clicks"]
        re = t["reach"]
        cpm = round(sp / im * 1000, 2) if im else 0
        cpc = round(sp / cl, 2) if cl else 0
        ctr = round(cl / im * 100, 2) if im else 0
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

    # Daily paid reach (sum of all campaigns that day)
    daily_paid_reach = []
    daily_spend = []
    for k in day_keys:
        rows_day = ads_by_date.get(k, [])
        daily_paid_reach.append(sum(int(r.get("reach") or 0) for r in rows_day))
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
    total_clicks       = sum(c["clicks"] for c in campaigns)

    organic_pct = round(total_organic / total_reach * 100, 1) if total_reach else 0
    paid_pct    = round(100 - organic_pct, 1)
    org_eng_rate = round(total_interactions / total_organic * 100, 2) if total_organic else 0
    avg_cpm = round(total_spend / total_impressions * 1000, 2) if total_impressions else 0
    avg_cpc = round(total_spend / total_clicks, 2) if total_clicks else 0

    followers   = int(profile_info.get("followers_count") or 0)
    following   = int(profile_info.get("follows_count") or 0)
    media       = int(profile_info.get("media_count") or 0)
    picture_url = profile_info.get("profile_picture_url", "")

    # Followers gained in period (from daily follower_count metric)
    followers_gained = sum(daily_follower_change)

    # Paid followers: from campaigns with follow/traffic objective
    traffic_clicks = sum(
        c["clicks"] for c in campaigns
        if "tráfego" in c["name"].lower() or "perfil" in c["name"].lower() or "traffic" in c["name"].lower()
    )
    followers_paid_est = max(0, int(traffic_clicks * 0.28))

    # If we have real data use it; otherwise fall back to estimate
    if followers_gained > 0:
        followers_organic_est = max(0, followers_gained - followers_paid_est)
    else:
        # No follower_count data available — use estimate only
        followers_gained      = followers_paid_est
        followers_organic_est = 0

    cost_per_follower = round(total_spend / max(1, followers_paid_est), 2) if total_spend else 0
    new_followers_est = followers_gained  # keep for backward compat

    period_label = f"{labels[0]} – {labels[-1]} {days[0].year}"

    return {
        "labels": labels,
        "days": len(days),
        "period_label": period_label,
        "date_from": date_from,
        "date_to": date_to,
        # Instagram
        "followers": followers,
        "following": following,
        "media": media,
        "picture_url": picture_url,
        "followers_gained": followers_gained,
        "followers_organic_est": followers_organic_est,
        "followers_paid_est": followers_paid_est,
        "total_reach": total_reach,
        "total_organic": total_organic,
        "total_paid_reach": total_paid_reach,
        "organic_pct": organic_pct,
        "paid_pct": paid_pct,
        "total_interactions": total_interactions,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_saves": total_saves,
        "total_shares": total_shares,
        "org_eng_rate": org_eng_rate,
        "new_followers_est": new_followers_est,
        "cost_per_follower": cost_per_follower,
        # Paid
        "total_spend": total_spend,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "avg_cpm": avg_cpm,
        "avg_cpc": avg_cpc,
        "campaigns": campaigns,
        # Daily arrays
        "daily_reach": daily_reach,
        "daily_organic_reach": daily_organic_reach,
        "daily_paid_reach": daily_paid_reach,
        "daily_likes": daily_likes,
        "daily_comments": daily_comments,
        "daily_saves": daily_saves,
        "daily_shares": daily_shares,
        "daily_interactions": daily_interactions,
        "daily_spend": daily_spend,
    }
