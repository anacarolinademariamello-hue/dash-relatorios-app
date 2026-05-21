"""
Daily paid-traffic alert script.
Run by GitHub Actions every day at 08:00 BRT (11:00 UTC).

Checks yesterday's Meta Ads metrics for ALL active clients and sends
an alert email via Resend if any threshold is exceeded.

Environment variables (GitHub Secrets):
  META_ACCESS_TOKEN    — long-lived Meta User Access Token
  SUPABASE_URL         — Supabase project REST URL
  SUPABASE_SERVICE_KEY — Supabase service_role key
  RESEND_API_KEY       — Resend API key
"""
import sys
import os
from datetime import date, timedelta

# Add project root to path so we can import src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.profiles import PROFILES
from src.api import fetch_meta_ads_daily
from src.alerts import check_ads_alerts, build_alert_email, send_email
from src import supabase_db


def main():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago  = (date.today() - timedelta(days=8)).isoformat()

    # Load client list: prefer Supabase, fall back to hardcoded profiles
    clients = supabase_db.get_clients() if supabase_db.is_configured() else {}
    if not clients:
        clients = PROFILES

    all_alerts: list[dict] = []

    for display_name, profile in clients.items():
        if not profile.get("facebook_account_id"):
            continue

        print(f"[check_ads] Checking {display_name}…")

        # Fetch yesterday's campaign data
        try:
            campaigns_today = fetch_meta_ads_daily(profile, yesterday, yesterday)
        except Exception as e:
            print(f"[check_ads]   Error fetching today's data: {e}")
            campaigns_today = []

        if not campaigns_today:
            print(f"[check_ads]   No campaign data for yesterday — skipping.")
            continue

        # Fetch last 7 days for spend spike comparison
        try:
            week_rows = fetch_meta_ads_daily(profile, week_ago, yesterday)
            daily_spend_7d = []
            for r in week_rows:
                if r.get("date", "")[:10] != yesterday:
                    daily_spend_7d.append(float(r.get("spend", 0)))
        except Exception:
            daily_spend_7d = []

        alerts = check_ads_alerts(
            client_name=display_name,
            client_key=profile["key"],
            campaigns_today=campaigns_today,
            daily_spend_7d=daily_spend_7d,
        )

        if alerts:
            print(f"[check_ads]   {len(alerts)} alert(s) found.")
            all_alerts.append({
                "client_name": profile.get("name", display_name),
                "handle":      profile.get("handle", ""),
                "alerts":      alerts,
            })
        else:
            print(f"[check_ads]   OK — no alerts.")

    if not all_alerts:
        print("[check_ads] All clients OK. No emails sent.")
        return

    # Envia um e-mail separado por cliente
    failed = []
    for entry in all_alerts:
        client_name = entry["client_name"]
        handle      = entry.get("handle", "")
        label       = f"{client_name} ({handle})" if handle else client_name
        subject     = f"🚨 Alerta Tráfego — {client_name} · {yesterday}"

        html = build_alert_email(
            client_name=label,
            check_date=yesterday,
            alerts=entry["alerts"],
        )

        sent = send_email(subject, html)
        if sent:
            print(f"[check_ads] E-mail enviado: {client_name}")
        else:
            print(f"[check_ads] Falha ao enviar: {client_name}")
            failed.append(client_name)

    if failed:
        print(f"[check_ads] Falha em {len(failed)} cliente(s): {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
