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
import requests as _requests
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
from src import health_score as hs

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


# ── Verificação do token Meta ─────────────────────────────────────────────────

def _check_token_expiry() -> dict:
    """
    Consulta o endpoint debug_token da Meta para saber quantos dias restam.
    Retorna {"days_left": int, "expires_at": str, "is_valid": bool}.
    Se não conseguir verificar, retorna {"days_left": None}.
    """
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        return {"days_left": None}
    try:
        resp = _requests.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": token, "access_token": token},
            timeout=10,
        )
        data = resp.json().get("data", {})
        if not data.get("is_valid"):
            return {"days_left": 0, "expires_at": "—", "is_valid": False}
        expires_at = data.get("expires_at", 0)
        if not expires_at:
            # Token sem expiração (raro — app token)
            return {"days_left": 999, "expires_at": "Sem expiração", "is_valid": True}
        exp_date   = datetime.utcfromtimestamp(expires_at).date()
        days_left  = (exp_date - date.today()).days
        return {
            "days_left":  days_left,
            "expires_at": exp_date.strftime("%d/%m/%Y"),
            "is_valid":   True,
        }
    except Exception as exc:
        log.warning("Não foi possível verificar o token Meta: %s", exc)
        return {"days_left": None}


def _send_token_alert(days_left: int, expires_at: str) -> None:
    """Envia e-mail de alerta quando o token Meta está prestes a expirar."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipients = [r.strip() for r in os.environ.get("EMAIL_TO", "").split(",") if r.strip()]
    if not (gmail_user and gmail_pass and recipients):
        return

    urgency_color = "#dc2626" if days_left <= 3 else "#f59e0b"
    urgency_label = "🔴 URGENTE" if days_left <= 3 else "⚠️ Atenção"
    urgency_msg   = (
        "O token <strong>já expirou ou expira hoje</strong>. Os relatórios desta semana <strong>não foram gerados</strong>."
        if days_left <= 0 else
        f"O token expira em <strong>{days_left} dia{'s' if days_left != 1 else ''}</strong> ({expires_at}). "
        f"Renove antes de {expires_at} para não interromper os relatórios."
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f3f8;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:24px 16px;">
  <div style="background:linear-gradient(135deg,#7f1d1d,#dc2626);border-radius:16px;padding:32px;color:#fff;text-align:center;margin-bottom:20px;">
    <div style="font-size:2.5rem;margin-bottom:8px;">🔑</div>
    <h1 style="margin:0 0 6px;font-size:1.4rem;font-weight:700;">{urgency_label} — Token Meta expirando</h1>
    <div style="opacity:.85;font-size:.9rem;">Dash Digital · Automação Semanal</div>
  </div>
  <div style="background:#fff;border:1px solid #fca5a5;border-radius:12px;padding:20px 24px;margin-bottom:16px;">
    <p style="margin:0 0 12px;font-size:.95rem;color:#374151;">{urgency_msg}</p>
    <hr style="border:none;border-top:1px solid #f3f4f6;margin:16px 0;">
    <p style="margin:0;font-size:.85rem;color:#6b7280;"><strong>Como renovar:</strong></p>
    <ol style="margin:8px 0 0;padding-left:20px;font-size:.85rem;color:#374151;line-height:1.8;">
      <li>Acesse <a href="https://developers.facebook.com/tools/explorer/" style="color:#003f7c;">Meta Graph API Explorer</a></li>
      <li>Gere um novo User Access Token com as permissões necessárias</li>
      <li>Troque pelo token longo: <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">fb_exchange_token</code></li>
      <li>Atualize <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">META_ACCESS_TOKEN</code> nos Secrets do GitHub e do Streamlit Cloud</li>
    </ol>
  </div>
  <div style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">
    Alerta gerado automaticamente · Dash Digital · @dashdgt
  </div>
</div>
</body>
</html>"""

    subject = f"🔑 {'TOKEN EXPIRADO' if days_left <= 0 else f'Token Meta expira em {days_left} dia(s)'} — Dash Digital"
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"Dash Digital Relatórios <{gmail_user}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo(); smtp.starttls()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, recipients, msg.as_bytes())
        log.info("✉ Alerta de token enviado para: %s", ", ".join(recipients))
    except Exception as exc:
        log.error("Falha ao enviar alerta de token: %s", exc)


# ── Score de Saúde ────────────────────────────────────────────────────────────

def _calculate_health_score(data: dict, prev_metrics: dict | None) -> dict:
    """Delega para src.health_score.calculate (módulo compartilhado com o app manual)."""
    return hs.calculate(data, prev_metrics)


def _build_score_section(health: dict) -> str:
    """Monta o bloco HTML do Score de Saúde para o e-mail individual."""
    if not health:
        return ""

    score     = health["score"]
    grade     = health["grade"]
    color     = health["color"]
    delta     = health.get("delta")
    breakdown = health.get("breakdown", {})

    delta_html = ""
    if delta is not None:
        d_sign  = "+" if delta >= 0 else ""
        d_color = "#16a34a" if delta >= 0 else "#dc2626"
        d_arrow = "▲" if delta >= 0 else "▼"
        delta_html = (
            f'<div style="font-size:.8rem;color:{d_color};margin-top:4px;">'
            f'{d_arrow} {d_sign}{delta} pts vs semana anterior</div>'
        )

    emoji = "🟢" if score >= 70 else "🟡" if score >= 55 else "🟠" if score >= 35 else "🔴"

    _label_map = [
        ("frequencia",   "Frequência de postagem",         20),
        ("engajamento",  "Engajamento orgânico",           25),
        ("crescimento",  "Crescimento de seguidores",      20),
        ("ctr",          "CTR de campanhas",               20),
        ("consistencia", "Consistência (vs sem. anterior)", 15),
    ]
    bars_html = ""
    for key, label, max_val in _label_map:
        val       = breakdown.get(key, 0)
        pct       = int(val / max_val * 100) if max_val else 0
        bar_color = "#16a34a" if pct >= 70 else "#d97706" if pct >= 40 else "#dc2626"
        bars_html += f"""
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:.75rem;color:#6b7280;margin-bottom:3px;">
            <span>{label}</span>
            <span style="font-weight:600;color:#374151;">{val}/{max_val}</span>
          </div>
          <div style="background:#f3f4f6;border-radius:4px;height:7px;">
            <div style="background:{bar_color};width:{pct}%;height:7px;border-radius:4px;"></div>
          </div>
        </div>"""

    return f"""
  <div style="background:#fff;border:2px solid {color};border-radius:14px;padding:20px 24px;margin-bottom:20px;">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px;">
      <div>
        <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#9ca3af;margin-bottom:4px;">Score de Saúde da Conta</div>
        <div style="font-size:2.8rem;font-weight:800;color:{color};line-height:1.1;">
          {score}<span style="font-size:1rem;font-weight:400;color:#9ca3af;">/100</span>
        </div>
        <div style="font-size:.95rem;font-weight:700;color:{color};margin-top:2px;">{grade}</div>
        {delta_html}
      </div>
      <div style="font-size:3.5rem;line-height:1;">{emoji}</div>
    </div>
    {bars_html}
  </div>"""


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


def _build_ai_section(ai_analysis: dict = None) -> str:
    """Monta o bloco HTML de análise estratégica para o e-mail."""
    if not ai_analysis or not isinstance(ai_analysis, dict):
        return ""

    import re as _re

    def _strip_html(text: str) -> str:
        return _re.sub(r"<[^>]+>", "", text or "")

    strengths  = ai_analysis.get("strengths", [])
    attentions = ai_analysis.get("attentions", [])
    if not strengths and not attentions:
        return ""

    def _items_html(items: list, color: str, bg: str) -> str:
        rows = ""
        for item in items:
            emoji = item[0] if isinstance(item, (list, tuple)) else item.get("emoji", "•")
            text  = item[1] if isinstance(item, (list, tuple)) else item.get("text", "")
            text  = _strip_html(str(text))
            rows += (
                f'<div style="display:flex;gap:10px;padding:10px 0;'
                f'border-bottom:1px solid {bg};">'
                f'<span style="font-size:1.1rem;flex-shrink:0;">{emoji}</span>'
                f'<span style="font-size:.85rem;color:#374151;line-height:1.6;">{text}</span>'
                f'</div>'
            )
        return rows

    strengths_html  = _items_html(strengths,  "#16a34a", "#f0fdf4")
    attentions_html = _items_html(attentions, "#d97706", "#fffbeb")

    return f"""
  <div style="margin-top:24px;">
    <h3 style="color:#003f7c;font-size:1rem;margin:0 0 12px;">🧭 Análise Estratégica da Semana</h3>

    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:16px 20px;margin-bottom:12px;">
      <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#16a34a;margin-bottom:8px;">
        ✅ Pontos Fortes
      </div>
      {strengths_html}
    </div>

    <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:12px;padding:16px 20px;">
      <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#d97706;margin-bottom:8px;">
        ⚠️ Pontos de Atenção
      </div>
      {attentions_html}
    </div>
  </div>"""


def _build_email_body(name: str, handle: str, data: dict, period: str, ai_analysis: dict = None, health_score: dict = None) -> str:
    """Monta o corpo HTML do e-mail com resumo das métricas e análise estratégica."""
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

  {_build_score_section(health_score)}

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

  {_build_ai_section(ai_analysis)}

  <!-- Anexo -->
  <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin-top:24px;font-size:.85rem;color:#374151;">
    📎 O relatório completo com gráficos está anexado a este e-mail como arquivo HTML.<br>
    <span style="color:#9ca3af;font-size:.78rem;">Abra o arquivo no navegador para visualizar. Para salvar como PDF, use Ctrl+P → Salvar como PDF.</span>
  </div>

  <!-- Footer -->
  <div style="text-align:center;margin-top:24px;font-size:.72rem;color:#9ca3af;">
    Gerado automaticamente em {generated_at} · Dash Digital · @dashdgt
  </div>

</div>
</body>
</html>"""


def _send_summary_email(scores: list, date_from: str, date_to: str) -> None:
    """Envia e-mail de visão geral com o score de saúde de todos os clientes."""
    if not scores or not _email_configured():
        return

    gmail_user   = os.environ.get("GMAIL_USER", "")
    gmail_pass   = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipients   = [r.strip() for r in os.environ.get("EMAIL_TO", "").split(",") if r.strip()]
    generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
    period       = f"{date_from} → {date_to}"

    rows_html = ""
    for s in sorted(scores, key=lambda x: x["score"], reverse=True):
        score = s["score"]
        grade = s["grade"]
        color = s["color"]
        name  = s["name"]
        handle = s.get("handle", "")
        delta  = s.get("delta")
        emoji  = "🟢" if score >= 70 else "🟡" if score >= 55 else "🟠" if score >= 35 else "🔴"

        delta_html = ""
        if delta is not None:
            d_sign  = "+" if delta >= 0 else ""
            d_color = "#16a34a" if delta >= 0 else "#dc2626"
            delta_html = f'<span style="font-size:.72rem;color:{d_color};margin-left:6px;">{d_sign}{delta}pts</span>'

        rows_html += f"""
        <tr>
          <td style="padding:14px 16px;border-bottom:1px solid #f3f4f6;">
            <div style="font-weight:600;font-size:.9rem;color:#111827;">{name}</div>
            <div style="font-size:.75rem;color:#9ca3af;">{handle}</div>
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #f3f4f6;text-align:center;">
            <span style="font-size:1.8rem;font-weight:800;color:{color};">{score}</span>
            <span style="font-size:.8rem;color:#9ca3af;">/100</span>
            {delta_html}
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #f3f4f6;text-align:center;">
            {emoji} <span style="font-size:.85rem;font-weight:600;color:{color};">{grade}</span>
          </td>
        </tr>"""

    critical = [s for s in scores if s["score"] < 55]
    alert_html = ""
    if critical:
        names_str = ", ".join(s["name"] for s in critical)
        alert_html = f"""
  <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:12px;padding:14px 18px;font-size:.82rem;color:#92400e;margin-bottom:20px;">
    ⚠️ Clientes que precisam de atenção esta semana: <strong>{names_str}</strong>. Verifique os relatórios individuais.
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f3f8;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:24px 16px;">

  <div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);border-radius:16px;padding:28px 32px;color:#fff;text-align:center;margin-bottom:20px;">
    <div style="font-size:2rem;margin-bottom:8px;">🏥</div>
    <h1 style="margin:0 0 6px;font-size:1.4rem;font-weight:700;">Score de Saúde — Visão Geral</h1>
    <div style="opacity:.85;font-size:.9rem;">Dash Digital · Semana de {period}</div>
  </div>

  <div style="background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;margin-bottom:20px;">
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f8fafc;">
          <th style="padding:10px 16px;text-align:left;font-size:.75rem;color:#6b7280;font-weight:600;">Cliente</th>
          <th style="padding:10px 16px;text-align:center;font-size:.75rem;color:#6b7280;font-weight:600;">Score</th>
          <th style="padding:10px 16px;text-align:center;font-size:.75rem;color:#6b7280;font-weight:600;">Situação</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  {alert_html}

  <div style="text-align:center;font-size:.72rem;color:#9ca3af;">
    Gerado automaticamente em {generated_at} · Dash Digital · @dashdgt
  </div>
</div>
</body>
</html>"""

    subject = f"🏥 Score de Saúde Semanal — {len(scores)} cliente{'s' if len(scores) != 1 else ''} · {date_from}"
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"Dash Digital Relatórios <{gmail_user}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo(); smtp.starttls()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, recipients, msg.as_bytes())
        log.info("✉ E-mail de resumo de saúde enviado para: %s", ", ".join(recipients))
    except Exception as exc:
        log.error("Falha ao enviar e-mail de resumo de saúde: %s", exc)


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

def process_client(profile_key: str, profile: dict, date_from: str, date_to: str) -> tuple:
    name   = profile.get("name", profile_key)
    handle = profile.get("handle", "")
    log.info("→ Processando: %s (%s a %s)", name, date_from, date_to)

    # 1. Busca dados
    try:
        fetched = _fetch_client_data(profile, date_from, date_to)
    except Exception as exc:
        log.error("  ✗ Erro ao buscar dados: %s", exc)
        return False, None

    if not fetched["ig_rows"]:
        log.warning("  ⚠ Nenhum dado de alcance no período — pulando.")
        return False, None

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
        return False, None

    # 3. Busca métricas do período anterior (para consistência e delta do score)
    prev_metrics = None
    try:
        prev_metrics = supabase_db.get_previous_metrics(profile_key, date_from, date_to, "Geral")
    except Exception:
        pass

    # 4. Calcula score de saúde
    health = _calculate_health_score(data, prev_metrics)
    data["health_score"] = health["score"]
    log.info("  ✓ Score de saúde: %d/100 (%s)", health["score"], health["grade"])

    # 5. Gera análise estratégica com IA ANTES de salvar (para persistir junto)
    ai_analysis = None
    try:
        ai_analysis = generate_strategic_analysis(data, profile, "Geral")
        if ai_analysis:
            log.info("  ✓ Análise estratégica gerada pela IA")
    except Exception:
        log.warning("  ⚠ Análise estratégica indisponível — usando fallback")

    # Converte ai_analysis para formato JSON seguro (listas em vez de tuplas)
    _ai_safe = None
    if ai_analysis and isinstance(ai_analysis, dict):
        try:
            _ai_safe = {
                "strengths":  [[e, t] for e, t in (ai_analysis.get("strengths") or [])],
                "attentions": [[e, t] for e, t in (ai_analysis.get("attentions") or [])],
            }
        except Exception:
            _ai_safe = None

    # 4. Salva em report_history (com análise estratégica embutida — alimenta a IA)
    ok = supabase_db.save_report_metrics(profile_key, date_from, date_to, "Geral", data, ai_strategic=_ai_safe)
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
        return ok, health  # métricas já foram salvas — retorna status delas

    # 6. Envia por e-mail (com score de saúde e análise estratégica no corpo)
    period   = data.get("period_label", f"{date_from} → {date_to}")
    subject  = f"📊 Relatório Semanal — {name} · {period}"
    filename = f"relatorio_{profile_key}_{date_from}_{date_to}.html"
    body     = _build_email_body(name, handle, data, period, ai_analysis=_ai_safe, health_score=health)
    send_email(subject, body, html_report, filename)

    return ok, health


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log.info("═══ Geração semanal de métricas + relatórios iniciada ═══")

    if not _check_env():
        sys.exit(1)

    # ── Verificação do token Meta — alerta se < 10 dias ───────────────────────
    token_info = _check_token_expiry()
    days_left  = token_info.get("days_left")
    if days_left is None:
        log.warning("Não foi possível verificar validade do token Meta.")
    elif days_left <= 0:
        log.error("🔴 Token Meta EXPIRADO — relatórios não serão gerados.")
        _send_token_alert(days_left, token_info.get("expires_at", "—"))
        sys.exit(1)
    elif days_left <= 10:
        log.warning("⚠️  Token Meta expira em %d dia(s) (%s) — enviando alerta.", days_left, token_info.get("expires_at"))
        _send_token_alert(days_left, token_info.get("expires_at", "—"))
    else:
        log.info("🔑 Token Meta válido — %d dias restantes (%s).", days_left, token_info.get("expires_at"))

    profiles = supabase_db.get_clients()
    if not profiles:
        log.error("Nenhum cliente ativo no Supabase.")
        sys.exit(1)

    log.info("Clientes: %d | E-mail configurado: %s", len(profiles), _email_configured())

    date_from, date_to = _last_week()
    log.info("Período: %s → %s\n", date_from, date_to)

    results = {"ok": [], "fail": [], "scores": []}
    for _, profile in profiles.items():
        client_key = profile.get("key")
        if not client_key:
            continue
        success, health = process_client(client_key, profile, date_from, date_to)
        (results["ok"] if success else results["fail"]).append(profile.get("name", client_key))
        if health:
            results["scores"].append({
                "name":   profile.get("name", client_key),
                "handle": profile.get("handle", ""),
                "score":  health["score"],
                "grade":  health["grade"],
                "color":  health["color"],
                "delta":  health.get("delta"),
            })
        log.info("")  # linha em branco entre clientes

    log.info("═══ Resumo ═══")
    log.info("✓ Sucesso: %d — %s", len(results["ok"]),   ", ".join(results["ok"])   or "—")
    log.info("✗ Falha:   %d — %s", len(results["fail"]), ", ".join(results["fail"]) or "—")

    # E-mail de visão geral com o score de saúde de todos os clientes
    if results["scores"]:
        log.info("Enviando e-mail de resumo de saúde...")
        _send_summary_email(results["scores"], date_from, date_to)

    if results["fail"] and not results["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
