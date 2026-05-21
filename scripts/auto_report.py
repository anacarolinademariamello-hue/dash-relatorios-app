"""
auto_report.py — Geração automática de relatórios via GitHub Actions.

Uso:
  python scripts/auto_report.py --mode weekly    # toda segunda (últimos 7 dias)
  python scripts/auto_report.py --mode monthly   # todo dia 1 (últimos 30 dias)

Variáveis de ambiente necessárias (GitHub Secrets):
  META_ACCESS_TOKEN
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
  RESEND_API_KEY
  REPORT_EMAIL           (destinatário dos e-mails de tráfego)
"""
from __future__ import annotations

import argparse
import os
import sys
import json
import traceback
from datetime import date, timedelta

# Garante que os módulos src/ sejam encontrados
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api       import (fetch_instagram_daily, fetch_instagram_profile,
                            fetch_instagram_audience, fetch_instagram_top_posts,
                            fetch_meta_ads_daily, fetch_meta_ads_totals)
from src.processor import process
from src.supabase_db import save_report_metrics
from src.profiles  import PROFILES


# ── Configuração ──────────────────────────────────────────────────────────────

REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "")
RESEND_KEY   = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL   = "relatorios@dash.digital"   # domínio verificado no Resend


# ── Helpers de data ───────────────────────────────────────────────────────────

def _date_range_weekly() -> tuple[str, str]:
    """Últimos 7 dias completos (seg → dom anterior)."""
    today    = date.today()
    date_to  = today - timedelta(days=1)          # ontem
    date_from = date_to - timedelta(days=6)       # 7 dias
    return date_from.isoformat(), date_to.isoformat()


def _date_range_monthly() -> tuple[str, str]:
    """Mês anterior completo (dia 1 → último dia do mês passado)."""
    today    = date.today()
    last_day = today.replace(day=1) - timedelta(days=1)   # último dia do mês anterior
    first_day = last_day.replace(day=1)
    return first_day.isoformat(), last_day.isoformat()


# ── Envio de e-mail via Resend ────────────────────────────────────────────────

def _send_email(to: str, subject: str, html: str) -> bool:
    if not RESEND_KEY or not to:
        print(f"  ⚠️  E-mail não enviado (RESEND_API_KEY ou REPORT_EMAIL não configurado)")
        return False
    import requests as req
    r = req.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
        json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
        timeout=15,
    )
    ok = r.status_code in (200, 201)
    if ok:
        print(f"  ✅  E-mail enviado para {to}")
    else:
        print(f"  ❌  Erro no e-mail: {r.status_code} {r.text[:200]}")
    return ok


# ── Template de e-mail de tráfego ─────────────────────────────────────────────

def _build_traffic_email(client_name: str, handle: str, date_from: str, date_to: str,
                          data: dict) -> str:
    spend      = data.get("total_spend", 0)
    paid_reach = data.get("total_paid_reach", 0)
    clicks     = data.get("total_clicks", 0)
    ctr        = data.get("avg_ctr", 0)
    cpm        = data.get("avg_cpm", 0)
    cpc        = data.get("avg_cpc", 0)
    campaigns  = data.get("campaigns", [])

    # Formata valores
    def brl(v): return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    def num(v): return f"{int(v):,}".replace(",", ".")
    def pct(v): return f"{float(v):.2f}%"

    camp_rows = ""
    for c in campaigns[:5]:
        status_color = "#10b981" if c.get("status") == "ACTIVE" else "#94a3b8"
        camp_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#334155;">{c.get('name','—')[:40]}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#334155;text-align:right;">{brl(c.get('spend',0))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#334155;text-align:right;">{pct(c.get('ctr',0))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#334155;text-align:right;">{brl(c.get('cpc',0))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;text-align:center;">
            <span style="background:{status_color}22;color:{status_color};padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;">
              {"ATIVA" if c.get('status')=='ACTIVE' else c.get('status','—')}
            </span>
          </td>
        </tr>"""

    camp_table = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:12px;">
      <thead>
        <tr style="background:#f8fafc;">
          <th style="padding:8px 12px;font-size:11px;color:#64748b;text-align:left;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">Campanha</th>
          <th style="padding:8px 12px;font-size:11px;color:#64748b;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">Investido</th>
          <th style="padding:8px 12px;font-size:11px;color:#64748b;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">CTR</th>
          <th style="padding:8px 12px;font-size:11px;color:#64748b;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">CPC</th>
          <th style="padding:8px 12px;font-size:11px;color:#64748b;text-align:center;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">Status</th>
        </tr>
      </thead>
      <tbody>{camp_rows}</tbody>
    </table>""" if campaigns else "<p style='color:#94a3b8;font-size:13px;'>Nenhuma campanha no período.</p>"

    df_fmt = date.fromisoformat(date_from).strftime("%d/%m/%Y")
    dt_fmt = date.fromisoformat(date_to).strftime("%d/%m/%Y")

    return f"""
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',sans-serif;">
<div style="max-width:620px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">

  <!-- Header -->
  <div style="background:#0d2137;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:rgba(255,255,255,.5);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;">Relatório de Tráfego Pago</div>
    <div style="font-size:22px;font-weight:700;color:#fff;">{client_name}</div>
    <div style="font-size:13px;color:rgba(255,255,255,.6);margin-top:2px;">{handle} · {df_fmt} – {dt_fmt}</div>
  </div>

  <!-- KPIs -->
  <div style="padding:24px 32px 8px;display:flex;gap:12px;flex-wrap:wrap;">
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #f8b940;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Total Investido</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{brl(spend)}</div>
    </div>
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #3b82f6;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Alcance Pago</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{num(paid_reach)}</div>
    </div>
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #10b981;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Cliques</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{num(clicks)}</div>
    </div>
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #8b5cf6;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">CTR médio</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{pct(ctr)}</div>
    </div>
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #f59e0b;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">CPM médio</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{brl(cpm)}</div>
    </div>
    <div style="flex:1;min-width:110px;background:#f8fafc;border-radius:10px;padding:14px 16px;border-left:4px solid #ef4444;">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">CPC médio</div>
      <div style="font-size:22px;font-weight:800;color:#0d2137;">{brl(cpc)}</div>
    </div>
  </div>

  <!-- Campanhas -->
  <div style="padding:16px 32px 28px;">
    <div style="font-size:13px;font-weight:700;color:#0d2137;margin-bottom:4px;">Campanhas do período</div>
    {camp_table}
  </div>

  <!-- Footer -->
  <div style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;">
    <p style="font-size:11px;color:#94a3b8;margin:0;">Dash Digital · Relatório gerado automaticamente · <a href="https://dash-relatorios-app.streamlit.app/" style="color:#3b82f6;">Acessar relatório completo</a></p>
  </div>

</div>
</body></html>"""


# ── Geração de relatório para um cliente ─────────────────────────────────────

def run_report(profile: dict, date_from: str, date_to: str,
               report_type: str, send_email: bool = False) -> bool:
    name   = profile["name"]
    handle = profile.get("handle", "")
    key    = profile["key"]
    print(f"\n{'='*56}")
    print(f"  {name} ({handle})  |  {date_from} → {date_to}  |  {report_type}")
    print(f"{'='*56}")

    try:
        print("  📡 Buscando dados do Instagram...")
        ig_rows      = fetch_instagram_daily(profile, date_from, date_to)
        profile_info = fetch_instagram_profile(profile)
        audience     = fetch_instagram_audience(profile)
        top_posts    = fetch_instagram_top_posts(profile, date_from, date_to)

        print("  📡 Buscando dados de Ads...")
        ads_rows  = fetch_meta_ads_daily(profile, date_from, date_to)
        ads_totals = fetch_meta_ads_totals(profile, date_from, date_to)

        print("  ⚙️  Processando métricas...")
        data = process(ig_rows, ads_rows, profile_info, audience, top_posts,
                       date_from, date_to, ads_totals)

        print("  💾 Salvando no Supabase...")
        ok = save_report_metrics(key, date_from, date_to, report_type, data)
        if ok:
            print(f"  ✅ Salvo com sucesso.")
        else:
            print(f"  ⚠️  Não foi possível salvar (Supabase não configurado?)")

        # E-mail de tráfego (apenas weekly)
        if send_email and REPORT_EMAIL:
            print(f"  📧 Enviando e-mail de tráfego para {REPORT_EMAIL}...")
            html = _build_traffic_email(name, handle, date_from, date_to, data)
            _send_email(
                to=REPORT_EMAIL,
                subject=f"[Tráfego] {name} · {date_from} → {date_to}",
                html=html,
            )

        return True

    except Exception as e:
        print(f"  ❌ ERRO: {e}")
        traceback.print_exc()
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["weekly", "monthly"], required=True)
    args = parser.parse_args()

    if args.mode == "weekly":
        date_from, date_to = _date_range_weekly()
        report_type = "Geral"
        send_email  = True
        print(f"\n🗓️  MODO SEMANAL — {date_from} → {date_to}\n")
    else:
        date_from, date_to = _date_range_monthly()
        report_type = "Geral"
        send_email  = False
        print(f"\n📅  MODO MENSAL — {date_from} → {date_to}\n")

    results = {}
    for profile_name, profile in PROFILES.items():
        ok = run_report(profile, date_from, date_to,
                        report_type, send_email=send_email)
        results[profile["key"]] = ok

    print(f"\n{'='*56}")
    print("RESULTADO FINAL:")
    for key, ok in results.items():
        print(f"  {'✅' if ok else '❌'}  {key}")

    failed = [k for k, ok in results.items() if not ok]
    if failed:
        print(f"\n{len(failed)} cliente(s) com falha: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"\nTodos os {len(results)} clientes processados com sucesso.")


if __name__ == "__main__":
    main()
