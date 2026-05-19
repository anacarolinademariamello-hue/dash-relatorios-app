"""
weekly_metrics.py — Geração automática de métricas + relatório semanal por e-mail.

Roda via GitHub Actions toda segunda-feira às 08:00 BRT.
Para cada cliente ativo no Supabase:
  1. Busca dados dos últimos 7 dias na Meta Graph API
  2. Processa as métricas
  3. Salva em report_history  (alimenta a IA do gerador de copies)
  4. Gera o relatório HTML completo
  5. Envia por e-mail com resumo + HTML como anexo

Variáveis de ambiente necessárias (GitHub Secrets):
  META_ACCESS_TOKEN      — token de acesso Meta
  SUPABASE_URL           — URL do projeto Supabase
  SUPABASE_SERVICE_KEY   — chave service_role do Supabase
  ANTHROPIC_API_KEY      — chave da API Anthropic (para análise estratégica)
  GMAIL_USER             — e-mail Gmail remetente (ex: relatorios@gmail.com)
  GMAIL_APP_PASSWORD     — senha de app do Gmail (não a senha normal)
  EMAIL_TO               — destinatário(s), separados por vírgula
"""
import os
import sys
import logging
import smtplib
from datetime import date, timedelta, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import (
    fetch_instagram_daily,
    fetch_instagram_profile,
    fetch_instagram_audience,
    fetch_instagram_top_posts,
    fetch_meta_ads_daily,
)
from src.processor import process
from src.html_gen import generate
from src.ai_strategic import generate_strategic_analysis
from src import supabase_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Verificação de ambiente ───────────────────────────────────────────────────

def _check_env() -> bool:
    required = ("META_ACCESS_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    missing  = [k for k in required if not os.environ.get(k)]
    if missing:
        log.error("Variáveis de ambiente ausentes: %s", ", ".join(missing))
        return False
    return True


def _email_configured() -> bool:
    return bool(
        os.environ.get("GMAIL_USER")
        and os.environ.get("GMAIL_APP_PASSWORD")
        and os.environ.get("EMAIL_TO")
    )


# ── Período ───────────────────────────────────────────────────────────────────

def _last_week() -> tuple[str, str]:
    today     = date.today()
    date_to   = today - timedelta(days=1)
    date_from = date_to - timedelta(days=6)
    return date_from.isoformat(), date_to.isoformat()


# ── Busca paralela ────────────────────────────────────────────────────────────

def _fetch_client_data(profile: dict, date_from: str, date_to: str) -> dict:
    tasks = [
        ("ig_rows",      fetch_instagram_daily,     (profile, date_from, date_to)),
        ("profile_info", fetch_instagram_profile,   (profile,)),
        ("audience",     fetch_instagram_audience,  (profile,)),
        ("top_posts",    fetch_instagram_top_posts, (profile, date_from, date_to)),
        ("ads_rows",     fetch_meta_ads_daily,      (profile, date_from, date_to)),
    ]
    defaults = {
        "ig_rows":     [],
        "profile_info":{},
        "audience":    {"gender_age": {}, "countries": {}},
        "top_posts":   [],
        "ads_rows":    [],
    }
    results = dict(defaults)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_key = {executor.submit(fn, *args): key for key, fn, args in tasks}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                if key in ("ig_rows", "profile_info"):
                    raise RuntimeError(f"Erro crítico ao buscar {key}: {exc}") from exc
                log.warning("  Falha ao buscar %s (usando padrão): %s", key, exc)
                results[key] = defaults[key]

    return results


# ── E-mail ────────────────────────────────────────────────────────────────────

def _br(v, decimals=0):
    try:
        s = f"{float(v):,.{decimals}f}" if decimals else f"{int(round(float(v))):,}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


def _build_email_body(name: str, handle: str, data: dict, period: str) -> str:
    """Monta o corpo HTML do e-mail com resumo das métricas."""
    reach       = _br(data.get("total_reach", 0))
    organic     = _br(data.get("total_organic", 0))
    org_pct     = data.get("organic_pct", 0)
    eng         = _br(data.get("org_eng_rate", 0), 2)
    interactions= _br(data.get("total_interactions", 0))
    saves       = _br(data.get("total_saves", 0))
    followers   = data.get("followers_gained", 0)
    followers_s = f"+{_br(followers)}" if followers >= 0 else _br(followers)
    spend       = _br(data.get("total_spend", 0), 2)
    ctr         = _br(data.get("avg_ctr", 0), 2)
    cpm         = _br(data.get("avg_cpm", 0), 2)
    best_fmt    = data.get("content", {}).get("best_format", "—")

    # Campanhas
    campaigns_rows = ""
    for c in data.get("campaigns", [])[:5]:
        status_colors = {
            "best":    ("#dcfce7", "#14532d", "🏆 Melhor"),
            "warning": ("#fef3c7", "#92400e", "⚠️ Revisar"),
            "ok":      ("#eff6ff", "#1e40af", "✅ OK"),
            "ended":   ("#f3f4f6", "#374151", "⏹ Encerrada"),
        }
        bg, tc, label = status_colors.get(c.get("status",""), ("#f3f4f6","#374151","—"))
        campaigns_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;">{c['name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;text-align:center;">{c.get('ctr',0):.2f}%</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;text-align:center;">R${c.get('cpm',0):.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;text-align:center;">R${c.get('cpc',0):.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;text-align:center;">
            <span style="background:{bg};color:{tc};font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:6px;">{label}</span>
          </td>
        </tr>"""

    campaigns_section = ""
    if campaigns_rows:
        campaigns_section = f"""
        <h3 style="color:#003f7c;font-size:1rem;margin:24px 0 12px;">💰 Campanhas da Semana</h3>
        <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;">
          <thead>
            <tr style="background:#f8fafc;">
              <th style="padding:10px 12px;text-align:left;font-size:.78rem;color:#6b7280;font-weight:600;">Campanha</th>
              <th style="padding:10px 12px;text-align:center;font-size:.78rem;color:#6b7280;font-weight:600;">CTR</th>
              <th style="padding:10px 12px;text-align:center;font-size:.78rem;color:#6b7280;font-weight:600;">CPM</th>
              <th style="padding:10px 12px;text-align:center;font-size:.78rem;color:#6b7280;font-weight:600;">CPC</th>
              <th style="padding:10px 12px;text-align:center;font-size:.78rem;color:#6b7280;font-weight:600;">Status</th>
            </tr>
          </thead>
          <tbody>{campaigns_rows}</tbody>
        </table>"""

    generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f3f8;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);border-radius:16px;padding:32px;color:#fff;margin-bottom:20px;text-align:center;">
    <div style="font-size:2rem;margin-bottom:8px;">📊</div>
    <h1 style="margin:0 0 6px;font-size:1.4rem;font-weight:700;">Relatório Semanal</h1>
    <div style="opacity:.85;font-size:.95rem;">{name} · {handle}</div>
    <div style="margin-top:12px;background:rgba(255,255,255,.15);border-radius:8px;padding:6px 16px;display:inline-block;font-size:.85rem;">
      📅 {period}
    </div>
  </div>

  <!-- KPIs orgânicos -->
  <h3 style="color:#003f7c;font-size:1rem;margin:0 0 12px;">📈 Métricas Orgânicas</h3>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:20px;">
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#003f7c;">{reach}</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">Alcance Total</div>
      <div style="font-size:.7rem;color:#9ca3af;">{org_pct:.0f}% orgânico</div>
    </div>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#003f7c;">{eng}%</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">Engajamento</div>
      <div style="font-size:.7rem;color:#9ca3af;">{interactions} interações</div>
    </div>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#{'16a34a' if followers >= 0 else 'dc2626'};">{followers_s}</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">Seguidores</div>
      <div style="font-size:.7rem;color:#9ca3af;">{saves} saves</div>
    </div>
  </div>

  <!-- KPIs pagos -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:20px;">
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#f97316;">R${spend}</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">Gasto em Ads</div>
    </div>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#f97316;">{ctr}%</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">CTR Médio</div>
    </div>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;text-align:center;">
      <div style="font-size:1.5rem;font-weight:700;color:#f97316;">R${cpm}</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:4px;">CPM Médio</div>
    </div>
  </div>

  <!-- Melhor formato -->
  <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:.88rem;color:#1e40af;">
    🎯 Formato com melhor desempenho na semana: <strong>{best_fmt}</strong>
  </div>

  {campaigns_section}

  <!-- Anexo -->
  <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin-top:24px;font-size:.85rem;color:#374151;">
    📎 O relatório completo com gráficos e análise estratégica está anexado a este e-mail como arquivo HTML.<br>
    <span style="color:#9ca3af;font-size:.78rem;">Abra o arquivo no navegador para visualizar. Para salvar como PDF, use Ctrl+P → Salvar como PDF.</span>
  </div>

  <!-- Footer -->
  <div style="text-align:center;margin-top:24px;font-size:.72rem;color:#9ca3af;">
    Gerado automaticamente em {generated_at} · Dash Digital · @dashdgt
  </div>

</div>
</body>
</html>"""


def send_email(subject: str, body_html: str, html_report: str, filename: str) -> bool:
    """Envia e-mail via Gmail SMTP com o relatório HTML como anexo."""
    gmail_user  = os.environ.get("GMAIL_USER", "")
    gmail_pass  = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipients  = [r.strip() for r in os.environ.get("EMAIL_TO", "").split(",") if r.strip()]

    if not (gmail_user and gmail_pass and recipients):
        log.warning("E-mail não configurado — pulando envio.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"Dash Digital Relatórios <{gmail_user}>"
    msg["To"]      = ", ".join(recipients)

    # Corpo HTML
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Anexo — relatório HTML completo
    attachment = MIMEBase("text", "html")
    attachment.set_payload(html_report.encode("utf-8"))
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    attachment.add_header("Content-Type", "text/html; charset=utf-8")
    msg.attach(attachment)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, recipients, msg.as_bytes())
        log.info("  ✉ E-mail enviado para: %s", ", ".join(recipients))
        return True
    except Exception as exc:
        log.error("  ✗ Falha ao enviar e-mail: %s", exc)
        return False


# ── Processa um cliente ───────────────────────────────────────────────────────

def process_client(profile_key: str, profile: dict, date_from: str, date_to: str) -> bool:
    name   = profile.get("name", profile_key)
    handle = profile.get("handle", "")
    log.info("→ Processando: %s (%s a %s)", name, date_from, date_to)

    # 1. Busca dados
    try:
        fetched = _fetch_client_data(profile, date_from, date_to)
    except Exception as exc:
        log.error("  ✗ Erro ao buscar dados: %s", exc)
        return False

    if not fetched["ig_rows"]:
        log.warning("  ⚠ Nenhum dado de alcance no período — pulando.")
        return False

    # 2. Processa métricas
    try:
        data = process(
            fetched["ig_rows"],
            fetched["ads_rows"],
            fetched["profile_info"],
            fetched["audience"],
            fetched["top_posts"],
            date_from,
            date_to,
        )
        data["nicho"]        = profile.get("nicho", "")
        data["sub_nicho"]    = profile.get("sub_nicho", "")
        data["publico_alvo"] = profile.get("publico_alvo", "")
    except Exception as exc:
        log.error("  ✗ Erro ao processar métricas: %s", exc)
        return False

    # 3. Gera análise estratégica com IA ANTES de salvar (para persistir junto)
    ai_analysis = None
    try:
        ai_analysis = generate_strategic_analysis(data, profile, "Geral")
        if ai_analysis:
            log.info("  ✓ Análise estratégica gerada pela IA")
    except Exception:
        log.warning("  ⚠ Análise estratégica indisponível — usando fallback")

    # 4. Salva em report_history (com análise estratégica embutida — alimenta a IA)
    ok = supabase_db.save_report_metrics(profile_key, date_from, date_to, "Geral", data, ai_strategic=ai_analysis)
    if ok:
        log.info("  ✓ Métricas salvas no Supabase")
    else:
        log.error("  ✗ Falha ao salvar métricas")

    # 5. Gera HTML do relatório
    try:
        generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
        html_report  = generate(
            profile, data, "Geral",
            generated_at=generated_at,
            ai_analysis=ai_analysis,
        )
        log.info("  ✓ Relatório HTML gerado")
    except Exception as exc:
        log.error("  ✗ Erro ao gerar HTML: %s", exc)
        return ok   # métricas já foram salvas — retorna status delas

    # 6. Envia por e-mail
    period   = data.get("period_label", f"{date_from} → {date_to}")
    subject  = f"📊 Relatório Semanal — {name} · {period}"
    filename = f"relatorio_{profile_key}_{date_from}_{date_to}.html"
    body     = _build_email_body(name, handle, data, period)
    send_email(subject, body, html_report, filename)

    return ok


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log.info("═══ Geração semanal de métricas + relatórios iniciada ═══")

    if not _check_env():
        sys.exit(1)

    profiles = supabase_db.get_clients()
    if not profiles:
        log.error("Nenhum cliente ativo no Supabase.")
        sys.exit(1)

    log.info("Clientes: %d | E-mail configurado: %s", len(profiles), _email_configured())

    date_from, date_to = _last_week()
    log.info("Período: %s → %s\n", date_from, date_to)

    results = {"ok": [], "fail": []}
    for _, profile in profiles.items():
        client_key = profile.get("key")
        if not client_key:
            continue
        success = process_client(client_key, profile, date_from, date_to)
        (results["ok"] if success else results["fail"]).append(profile.get("name", client_key))
        log.info("")  # linha em branco entre clientes

    log.info("═══ Resumo ═══")
    log.info("✓ Sucesso: %d — %s", len(results["ok"]),   ", ".join(results["ok"])   or "—")
    log.info("✗ Falha:   %d — %s", len(results["fail"]), ", ".join(results["fail"]) or "—")

    if results["fail"] and not results["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
