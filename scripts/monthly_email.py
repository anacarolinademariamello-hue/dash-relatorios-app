"""
Monthly performance summary email script.
Run by GitHub Actions on the 1st of each month at 09:00 BRT.

Fetches last month's metrics from report_history (Supabase) for all active clients
and sends a summary email via Resend.

If no history exists for a client, fetches data live from the Meta API.

Environment variables (GitHub Secrets):
  META_ACCESS_TOKEN    — long-lived Meta User Access Token
  SUPABASE_URL         — Supabase project REST URL
  SUPABASE_SERVICE_KEY — Supabase service_role key
  RESEND_API_KEY       — Resend API key
"""
import sys
import os
from datetime import date
import calendar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.profiles import PROFILES
from src.api import (
    fetch_instagram_daily, fetch_instagram_profile,
    fetch_instagram_audience, fetch_instagram_top_posts,
    fetch_meta_ads_daily,
)
from src.processor import process
from src.alerts import build_monthly_email, send_email
from src import supabase_db


def _last_month_range() -> tuple[str, str]:
    """Return (date_from, date_to) for the previous calendar month."""
    today = date.today()
    first_this_month = today.replace(day=1)
    last_month_end   = first_this_month - __import__("datetime").timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.isoformat(), last_month_end.isoformat()


def _period_label(date_from: str, date_to: str) -> str:
    months_pt = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    d = date.fromisoformat(date_from)
    return f"{months_pt[d.month]} {d.year}"


def main():
    date_from, date_to = _last_month_range()
    period_label = _period_label(date_from, date_to)
    print(f"[monthly] Period: {date_from} to {date_to} ({period_label})")

    clients = supabase_db.get_clients() if supabase_db.is_configured() else {}
    if not clients:
        clients = PROFILES

    sent_count = 0

    for display_name, profile in clients.items():
        print(f"[monthly] Processing {display_name}…")

        # Try Supabase history first (fast)
        metrics = None
        prev_metrics = None

        if supabase_db.is_configured():
            history = supabase_db.get_history_list(profile["key"], limit=2)
            # Look for entry matching last month
            for entry in history:
                if entry.get("date_from") == date_from and entry.get("date_to") == date_to:
                    metrics = entry.get("metrics", {})
                    break

            # Previous period for comparison
            if metrics:
                prev_metrics = supabase_db.get_previous_metrics(
                    profile["key"], date_from, date_to, "Geral"
                )

        # Fallback: fetch live from API
        if not metrics:
            print(f"[monthly]   No history found — fetching from Meta API…")
            try:
                ig_rows      = fetch_instagram_daily(profile, date_from, date_to)
                profile_info = fetch_instagram_profile(profile)
                audience     = fetch_instagram_audience(profile)
                top_posts    = fetch_instagram_top_posts(profile, date_from, date_to)
                ads_rows     = fetch_meta_ads_daily(profile, date_from, date_to)
                data = process(ig_rows, ads_rows, profile_info, audience, top_posts, date_from, date_to)
                metrics = data
            except Exception as e:
                print(f"[monthly]   Error fetching data: {e} — skipping.")
                continue

        if not metrics:
            print(f"[monthly]   No metrics available — skipping.")
            continue

        html = build_monthly_email(
            client_name=display_name,
            period_label=period_label,
            metrics=metrics,
            prev_metrics=prev_metrics,
        )

        subject = f"📊 Relatório Mensal — {display_name} · {period_label}"
        sent = send_email(subject, html)

        if sent:
            print(f"[monthly]   ✅ Email sent for {display_name}.")
            sent_count += 1
        else:
            print(f"[monthly]   ❌ Failed to send email for {display_name}.")

    print(f"[monthly] Done. {sent_count}/{len(clients)} emails sent.")
    if sent_count < len(clients):
        sys.exit(1)


if __name__ == "__main__":
    main()
