"""
Alert logic for paid traffic monitoring.
Called by GitHub Actions daily workflow (scripts/check_ads_alerts.py).

Thresholds (adjustable):
  CPM_LIMIT      — alert if any campaign CPM > R$ 20
  CTR_MIN        — alert if any campaign CTR < 1.5 %
  ZERO_SPEND_MIN — alert if total daily spend = 0 but there are active campaigns
  SPEND_SPIKE    — alert if daily spend > 2× the 7-day average
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Optional

import requests

# ── Thresholds ─────────────────────────────────────────────────────────────────
CPM_LIMIT   = 20.0   # R$
CTR_MIN     = 1.5    # %
SPEND_SPIKE = 2.0    # multiplier vs 7-day avg

# ── Resend ─────────────────────────────────────────────────────────────────────
RESEND_API_URL = "https://api.resend.com/emails"
SENDER         = "onboarding@resend.dev"
RECIPIENT      = os.environ.get("EMAIL_TO", "anacarolinademariamello@gmail.com")


def _resend_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("resend_api_key", "") or ""
    except Exception:
        return os.environ.get("RESEND_API_KEY", "")


def send_email(subject: str, html_body: str) -> bool:
    """Send email via Resend API. Returns True on success."""
    key = _resend_key()
    if not key:
        print("[alerts] RESEND_API_KEY not configured — email not sent.")
        return False

    payload = {
        "from":    SENDER,
        "to":      [RECIPIENT],
        "subject": subject,
        "html":    html_body,
    }
    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=20,
        )
        ok = resp.status_code in (200, 201)
        if not ok:
            print(f"[alerts] Resend error {resp.status_code}: {resp.text}")
        return ok
    except Exception as e:
        print(f"[alerts] Resend exception: {e}")
        return False


def check_ads_alerts(
    client_name: str,
    client_key: str,
    campaigns_today: list,
    daily_spend_7d: list,
) -> list[dict]:
    """
    Analyse today's campaign data and return a list of alert dicts.
    Each alert: {level: "warning"|"critical", message: str}

    campaigns_today: list of campaign rows for yesterday
    daily_spend_7d:  list of float spend values for the last 7 days (oldest first)
    """
    alerts: list[dict] = []

    total_spend = sum(float(c.get("spend", 0)) for c in campaigns_today)

    # ── Zero spend (campaigns exist but nothing spent) ─────────────────────────
    if campaigns_today and total_spend == 0:
        alerts.append({
            "level":   "critical",
            "message": f"⛔ Gasto zero ontem apesar de {len(campaigns_today)} campanha(s) ativa(s). "
                       f"Verifique se há orçamento suficiente ou bloqueio de conta.",
        })

    # ── Spend spike vs 7-day average ──────────────────────────────────────────
    if daily_spend_7d and total_spend > 0:
        avg7 = sum(daily_spend_7d) / len(daily_spend_7d)
        if avg7 > 0 and total_spend > avg7 * SPEND_SPIKE:
            alerts.append({
                "level":   "warning",
                "message": f"📈 Gasto de ontem (R$ {total_spend:.2f}) foi {total_spend/avg7:.1f}× "
                           f"acima da média de 7 dias (R$ {avg7:.2f}). Verifique budget.",
            })

    # ── Per-campaign checks ────────────────────────────────────────────────────
    for c in campaigns_today:
        name = c.get("campaign_name", "Campanha")
        cpm  = float(c.get("cpm", 0))
        ctr  = float(c.get("ctr", 0))
        imp  = int(c.get("impressions", 0))

        if cpm > CPM_LIMIT and imp > 0:
            alerts.append({
                "level":   "warning",
                "message": f"⚠️ CPM elevado na campanha <em>{name}</em>: "
                           f"R$ {cpm:.2f} (limite: R$ {CPM_LIMIT:.2f}).",
            })

        if 0 < ctr < CTR_MIN and imp > 0:
            alerts.append({
                "level":   "warning",
                "message": f"⚠️ CTR baixo na campanha <em>{name}</em>: "
                           f"{ctr:.2f}% (mínimo: {CTR_MIN:.1f}%). "
                           f"Considere revisar o criativo ou a segmentação.",
            })

        if imp == 0 and float(c.get("spend", 0)) > 0:
            alerts.append({
                "level":   "critical",
                "message": f"⛔ Campanha <em>{name}</em> gastou R$ {float(c.get('spend',0)):.2f} "
                           f"mas não gerou impressões. Pode haver rejeição de anúncio.",
            })

    return alerts


def build_alert_email(client_name: str, check_date: str, alerts: list[dict]) -> str:
    """Build HTML email body for ad alerts."""
    rows = ""
    for a in alerts:
        color = "#dc2626" if a["level"] == "critical" else "#d97706"
        bg    = "#fef2f2" if a["level"] == "critical" else "#fffbeb"
        rows += (
            f'<tr><td style="padding:10px 16px;background:{bg};border-left:4px solid {color};'
            f'border-bottom:1px solid #e5e7eb;font-size:14px;color:#1f2937;">'
            f'{a["message"]}</td></tr>'
        )

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
            overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.10);">
  <div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);padding:24px 28px;color:#fff;">
    <div style="font-size:1.3rem;font-weight:700;">🚨 Alerta de Tráfego Pago</div>
    <div style="font-size:.9rem;opacity:.8;margin-top:4px;">
      {client_name} · {check_date}
    </div>
  </div>
  <div style="padding:20px 28px 8px;">
    <p style="color:#374151;font-size:.95rem;margin-bottom:16px;">
      Foram detectados <strong>{len(alerts)} alerta(s)</strong> nas campanhas de Meta Ads de ontem:
    </p>
    <table style="width:100%;border-collapse:collapse;">{rows}</table>
  </div>
  <div style="padding:20px 28px;border-top:1px solid #e5e7eb;margin-top:12px;">
    <p style="font-size:.8rem;color:#9ca3af;">
      Este alerta foi gerado automaticamente pelo sistema Dash Digital.<br>
      Acesse o <a href="https://business.facebook.com" style="color:#003f7c;">Meta Ads Manager</a>
      para verificar e corrigir os problemas.
    </p>
  </div>
</div>
</body></html>"""


def build_monthly_email(
    client_name: str,
    period_label: str,
    metrics: dict,
    prev_metrics: Optional[dict] = None,
) -> str:
    """Build HTML email body for monthly summary report."""

    def _fmt(v, dec=0):
        try:
            if dec:
                return f"{float(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{int(round(float(v))):,}".replace(",", ".")
        except Exception:
            return str(v)

    def _delta(key):
        if not prev_metrics:
            return ""
        curr = float(metrics.get(key, 0))
        prev = float(prev_metrics.get(key, 0))
        if prev == 0:
            return ""
        pct = (curr - prev) / prev * 100
        arrow = "↑" if pct >= 0 else "↓"
        color = "#16a34a" if pct >= 0 else "#dc2626"
        return (
            f'<span style="font-size:12px;color:{color};margin-left:6px;">'
            f'{arrow} {abs(pct):.1f}%</span>'
        )

    rows = [
        ("📡", "Alcance Total",     _fmt(metrics.get("total_reach", 0)),        _delta("total_reach")),
        ("🌱", "Alcance Orgânico",  _fmt(metrics.get("total_organic", 0)),       _delta("total_organic")),
        ("💬", "Interações",        _fmt(metrics.get("total_interactions", 0)),  _delta("total_interactions")),
        ("📊", "Eng. Orgânico",     f'{_fmt(metrics.get("org_eng_rate", 0), 2)}%', _delta("org_eng_rate")),
        ("❤️", "Curtidas",          _fmt(metrics.get("total_likes", 0)),         _delta("total_likes")),
        ("💾", "Salvamentos",       _fmt(metrics.get("total_saves", 0)),         _delta("total_saves")),
        ("📈", "Seguidores Ganhos", f'+{_fmt(metrics.get("followers_gained", 0))}', _delta("followers_gained")),
        ("💰", "Investimento Ads",  f'R$ {_fmt(metrics.get("total_spend", 0), 2)}', _delta("total_spend")),
        ("🎯", "Alcance Pago",      _fmt(metrics.get("total_paid_reach", 0)),    _delta("total_paid_reach")),
        ("👆", "Cliques (Ads)",     _fmt(metrics.get("total_clicks", 0)),        _delta("total_clicks")),
    ]

    kpi_rows = ""
    for i, (icon, label, val, delta) in enumerate(rows):
        bg = "#f9fafb" if i % 2 == 0 else "#fff"
        kpi_rows += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:10px 16px;font-size:14px;color:#6b7280;">{icon} {label}</td>'
            f'<td style="padding:10px 16px;font-size:14px;font-weight:700;color:#1f2937;">'
            f'{val}{delta}</td></tr>'
        )

    prev_note = ""
    if prev_metrics:
        prev_note = "<p style='font-size:12px;color:#9ca3af;'>As setas indicam comparação com o período equivalente anterior.</p>"

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
            overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.10);">
  <div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);padding:24px 28px;color:#fff;">
    <div style="font-size:1.3rem;font-weight:700;">📊 Relatório Mensal de Performance</div>
    <div style="font-size:.9rem;opacity:.8;margin-top:4px;">
      {client_name} · {period_label}
    </div>
  </div>
  <div style="padding:20px 28px 8px;">
    <p style="color:#374151;font-size:.95rem;margin-bottom:16px;">
      Aqui está o resumo de performance do período <strong>{period_label}</strong>:
    </p>
    <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;
                  border:1px solid #e5e7eb;">{kpi_rows}</table>
    {prev_note}
  </div>
  <div style="padding:20px 28px;border-top:1px solid #e5e7eb;margin-top:12px;">
    <p style="font-size:.8rem;color:#9ca3af;">
      Relatório gerado automaticamente por <strong>Dash Digital</strong>.<br>
      Para o relatório completo com gráficos, acesse o
      <a href="https://dash-relatorios.streamlit.app" style="color:#003f7c;">painel de relatórios</a>.
    </p>
  </div>
</div>
</body></html>"""
