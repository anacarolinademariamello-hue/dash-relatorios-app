import base64
import csv
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta, datetime

import streamlit as st
import streamlit.components.v1 as components

from src.profiles import PROFILES
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


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_all_data(profile_key: str, date_from: str, date_to: str, report_type: str, profile: dict = None) -> dict:
    """
    Busca todos os dados Meta em paralelo (5 requisições simultâneas).
    Resultado em cache por 30 min — nova geração para o mesmo período
    é instantânea até o token expirar ou o TTL vencer.
    """
    if profile is None:
        # Fallback: busca por key dentro de PROFILES (chaves são display names)
        profile = next(
            (p for p in PROFILES.values() if p.get("key") == profile_key),
            None,
        )
        if profile is None:
            raise ValueError(f"Perfil '{profile_key}' não encontrado.")

    tasks = [
        ("ig_rows",      fetch_instagram_daily,    (profile, date_from, date_to)),
        ("profile_info", fetch_instagram_profile,  (profile,)),
        ("audience",     fetch_instagram_audience, (profile,)),
        ("top_posts",    fetch_instagram_top_posts,(profile, date_from, date_to)),
    ]
    if report_type != "Só Orgânico":
        tasks.append(("ads_rows", fetch_meta_ads_daily, (profile, date_from, date_to)))

    defaults = {
        "ig_rows":     [],
        "profile_info":{},
        "audience":    {"gender_age": {}, "countries": {}},
        "top_posts":   [],
        "ads_rows":    [],
    }
    results = dict(defaults)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_key = {
            executor.submit(fn, *args): key
            for key, fn, args in tasks
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except (PermissionError, ValueError):
                raise  # erros críticos de auth/config — propagar sempre
            except Exception:
                if key in ("ig_rows", "profile_info"):
                    raise  # dados principais — propagar
                results[key] = defaults[key]  # não-crítico — usa padrão

    return results


def _make_csv(data: dict) -> str:
    """Gera CSV com métricas diárias + campanhas para download."""
    output = io.StringIO()
    w = csv.writer(output)

    # Métricas diárias
    w.writerow(["=== MÉTRICAS DIÁRIAS ==="])
    w.writerow([
        "Data", "Alcance Total", "Alcance Orgânico", "Alcance Pago",
        "Curtidas", "Comentários", "Salvamentos", "Compartilhamentos",
        "Interações Totais", "Seguidores Ganhos", "Gasto Ads (R$)",
    ])
    labels = data.get("labels", [])
    for i, label in enumerate(labels):
        w.writerow([
            label,
            data["daily_reach"][i],
            data["daily_organic_reach"][i],
            data["daily_paid_reach"][i],
            data["daily_likes"][i],
            data["daily_comments"][i],
            data["daily_saves"][i],
            data["daily_shares"][i],
            data["daily_interactions"][i],
            data["daily_follower_change"][i],
            data["daily_spend"][i] if data.get("daily_spend") else 0,
        ])

    # Campanhas
    if data.get("campaigns"):
        w.writerow([])
        w.writerow(["=== CAMPANHAS META ADS ==="])
        w.writerow(["Campanha", "Objetivo", "Gasto (R$)", "Impressões",
                    "Alcance", "Cliques", "CPM", "CPC", "CTR (%)"])
        for c in data["campaigns"]:
            w.writerow([
                c["name"], c["objective"], c["spend"], c["impressions"],
                c["reach"], c["clicks"], c["cpm"], c["cpc"], c["ctr"],
            ])

    return output.getvalue()


@st.cache_data(ttl=300, show_spinner=False)
def _load_profiles() -> dict:
    """
    Load client profiles: Supabase first, fall back to profiles.py.
    Cached for 5 minutes so profile changes appear quickly.
    """
    db_profiles = supabase_db.get_clients()
    if db_profiles:
        return db_profiles
    return PROFILES


def _trending_badges(current: dict, previous: dict) -> str:
    """
    Build an HTML string with delta badges comparing current vs previous metrics.
    Shown between the success banner and the report iframe.
    """
    def _delta(key, label, prefix="", suffix="", decimals=0):
        c = float(current.get(key, 0))
        p = float(previous.get(key, 0))
        if p == 0:
            return ""
        pct = (c - p) / p * 100
        arrow  = "↑" if pct >= 0 else "↓"
        color  = "#16a34a" if pct >= 0 else "#dc2626"
        bg     = "#f0fdf4" if pct >= 0 else "#fef2f2"
        border = "#bbf7d0" if pct >= 0 else "#fecaca"
        if decimals:
            val_str = f"{prefix}{c:,.{decimals}f}{suffix}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            val_str = f"{prefix}{int(round(c)):,}{suffix}".replace(",", ".")
        return (
            f'<div style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{bg};border:1px solid {border};border-radius:8px;'
            f'padding:5px 10px;font-size:.8rem;white-space:nowrap;">'
            f'<span style="color:#374151;">{label}</span>'
            f'<strong style="color:#111;">{val_str}</strong>'
            f'<span style="color:{color};font-weight:700;">{arrow} {abs(pct):.1f}%</span>'
            f'</div>'
        )

    badges = [
        _delta("total_reach",        "📡 Alcance"),
        _delta("total_organic",      "🌱 Orgânico"),
        _delta("total_interactions", "💬 Interações"),
        _delta("org_eng_rate",       "📊 Eng.", suffix="%", decimals=2),
        _delta("total_saves",        "💾 Saves"),
        _delta("followers_gained",   "📈 Seguidores", prefix="+"),
        _delta("total_spend",        "💰 Gasto", prefix="R$", decimals=2),
    ]
    badges = [b for b in badges if b]  # remove empty

    if not badges:
        return ""

    return (
        '<div style="background:#fff;border:1px solid #dde3ed;border-radius:12px;'
        'padding:14px 18px;margin-bottom:12px;">'
        '<div style="font-size:.78rem;color:#6b7280;font-weight:600;'
        'text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;">'
        '📊 Comparativo vs período anterior</div>'
        '<div style="display:flex;flex-wrap:wrap;gap:8px;">'
        + "".join(badges)
        + '</div></div>'
    )


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dash Digital — Relatórios",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom sidebar CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] {background:#0d2137;}

/* labels e textos gerais */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color:#fff !important;
}

/* campos de input (selectbox, date) — fundo escuro + texto branco */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] textarea {
    background-color:#1a3a5c !important;
    color:#fff !important;
    border:1px solid rgba(255,255,255,0.25) !important;
    border-radius:8px !important;
}

/* container visual do selectbox */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] [data-baseweb="base-input"] {
    background-color:#1a3a5c !important;
    border-color:rgba(255,255,255,0.25) !important;
    border-radius:8px !important;
    color:#fff !important;
}

/* área de clique do selectbox — aumenta padding para facilitar o clique */
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
[data-testid="stSidebar"] [data-baseweb="select"] [role="button"],
[data-testid="stSidebar"] [data-baseweb="select"] > div > div {
    min-height:42px !important;
    padding-top:8px !important;
    padding-bottom:8px !important;
    cursor:pointer !important;
}

/* texto dentro do selectbox */
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div {
    color:#fff !important;
}

/* ícone de seta do selectbox */
[data-testid="stSidebar"] [data-baseweb="select"] svg {
    fill:#fff !important;
}

/* ícone de calendário */
[data-testid="stSidebar"] [data-testid="stDateInput"] svg,
[data-testid="stSidebar"] button[kind="icon"] svg {
    color:#fff !important;
    fill:#fff !important;
}

/* radio buttons */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color:rgba(255,255,255,0.90) !important;
}

/* botão gerar */
[data-testid="stSidebar"] .stButton>button {
    background:linear-gradient(135deg,#f8b940,#d99a20);
    color:#003f7c !important;
    font-weight:700;
    border:none;
    border-radius:10px;
    padding:12px;
    font-size:1rem;
    width:100%;
    margin-top:8px;
}
[data-testid="stSidebar"] .stButton>button:hover {
    background:linear-gradient(135deg,#ffc94d,#e8aa30);
    transform:translateY(-1px);
}

/* Navegação entre páginas — estilizada para o tema escuro */
div[data-testid="stSidebarNav"] {display:block;}
div[data-testid="stSidebarNav"] a {
    color:rgba(255,255,255,0.80) !important;
    border-radius:8px;
    padding:6px 10px;
}
div[data-testid="stSidebarNav"] a:hover,
div[data-testid="stSidebarNav"] a[aria-selected="true"] {
    background:rgba(255,255,255,0.12) !important;
    color:#fff !important;
}

/* link "Gerenciar Clientes" no sidebar */
[data-testid="stSidebar"] [data-testid="stPageLink"] a,
[data-testid="stSidebar"] [data-testid="stPageLink"] p {
    color:rgba(255,255,255,0.75) !important;
    font-size:0.88rem !important;
    text-decoration:none !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover a,
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover p {
    color:#fff !important;
}

/* ── Main area ─────────────────────────────────────────── */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1100px;
    background: #f0f3f8;
}
.page-header {
    background: linear-gradient(135deg, #003f7c 0%, #1a5a9a 60%, #0d4080 100%);
    border-radius: 16px;
    padding: 26px 32px;
    color: #fff;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.page-header::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at 85% 15%, rgba(255,255,255,0.10) 0%, transparent 60%);
    pointer-events: none;
}
.page-header-title { font-size: 1.45rem; font-weight: 700; color: #fff; margin-bottom: 4px; }
.page-header-sub   { font-size: 0.88rem; color: rgba(255,255,255,0.62); }
.welcome-card {
    background: #fff;
    border: 1px solid #dde3ed;
    border-radius: 16px;
    padding: 48px 32px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# ── Logo ─────────────────────────────────────────────────────────────────────
def _get_logo_b64() -> str:
    try:
        with open("assets/logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_logo_b64 = _get_logo_b64()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    if _logo_b64:
        st.markdown(
            f'<div style="padding:12px 4px 8px;">'
            f'<img src="data:image/png;base64,{_logo_b64}" '
            f'style="height:38px;">'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 📊 Dash Digital")

    # ── Sidebar do Gerador de Relatórios ──────────────────────────────────
    st.markdown("**Gerador de Relatórios**")
    st.markdown("---")

    _all_profiles = _load_profiles()
    profile_name = st.selectbox(
        "Perfil",
        list(_all_profiles.keys()),
        help="Selecione o cliente",
    )

    st.markdown("**Período**")
    col1, col2 = st.columns(2)
    default_end   = date.today() - timedelta(days=1)
    default_start = default_end - timedelta(days=29)
    date_from = col1.date_input("De",   value=default_start, format="DD/MM/YYYY")
    date_to   = col2.date_input("Até",  value=default_end,   format="DD/MM/YYYY")

    report_type = st.radio(
        "Tipo de Relatório",
        ["Geral", "Só Orgânico", "Só Pago"],
        index=0,
        help="Geral: tudo | Só Orgânico: sem seção de ads | Só Pago: foco em campanhas",
    )

    # ── Status do token Meta ──────────────────────────────────────────────
    _token_ok    = True
    _token_msg   = ""
    _token_level = ""

    try:
        _meta_token = st.secrets.get("meta_access_token", "") or ""
        _created_str = st.secrets.get("meta_token_created", "") or ""

        if not _meta_token:
            _token_ok    = False
            _token_level = "missing"
            _token_msg   = (
                "🔴 <strong>Token Meta não configurado!</strong><br>"
                "Adicione <code>meta_access_token</code> em Secrets."
            )
        elif _created_str:
            _created  = datetime.strptime(_created_str, "%Y-%m-%d").date()
            _expires  = _created + timedelta(days=60)
            _days_left = (_expires - date.today()).days

            if _days_left <= 0:
                _token_ok    = False
                _token_level = "error"
                _token_msg   = (
                    "🔴 <strong>Token Meta expirado!</strong><br>"
                    "Renove o token para gerar relatórios."
                )
            elif _days_left <= 10:
                _token_level = "warning"
                _token_msg   = (
                    f"⚠️ <strong>Token expira em {_days_left} dias</strong><br>"
                    f"Renove antes de {_expires.strftime('%d/%m/%Y')}."
                )
            else:
                _token_level = "ok"
                _token_msg   = f"🔑 Token válido por mais {_days_left} dias"
    except Exception:
        pass

    _btn_label = "🚀 Gerar Relatório" if _token_ok else "⛔ Token inválido — não é possível gerar"
    gerar = st.button(_btn_label, use_container_width=True, disabled=not _token_ok)

    st.markdown("---")
    if _token_level in ("missing", "error"):
        st.markdown(
            f"<div style='background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;"
            f"padding:10px 12px;font-size:.78rem;color:#991b1b;margin-bottom:8px;'>{_token_msg}</div>",
            unsafe_allow_html=True,
        )
    elif _token_level == "warning":
        st.markdown(
            f"<div style='background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;"
            f"padding:10px 12px;font-size:.78rem;color:#92400e;margin-bottom:8px;'>{_token_msg}</div>",
            unsafe_allow_html=True,
        )
    elif _token_level == "ok":
        st.markdown(
            f"<small style='opacity:.45;font-size:.7rem;'>{_token_msg}</small>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<small style='opacity:.55'>Os dados são buscados em tempo real<br>via Instagram Insights + Meta Ads</small>",
        unsafe_allow_html=True,
    )


# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-header">
    <div class="page-header-title">📊 Gerador de Relatórios · Meta</div>
    <div class="page-header-sub">Selecione o perfil e o período na barra lateral, depois clique em Gerar Relatório</div>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for _k, _v in [("report_html", None), ("report_label", ""), ("report_file", ""),
               ("report_data", None), ("report_config", ""), ("report_prev", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Aviso de relatório desatualizado ──────────────────────────────────────────
_current_config = f"{profile_name}|{date_from}|{date_to}|{report_type}"
if st.session_state.report_html and st.session_state.report_config != _current_config:
    st.warning("⚠️ As configurações mudaram. Clique em **Gerar Relatório** para atualizar.")

if gerar:
    # ── Validações ───────────────────────────────────────────────────────────
    if date_from > date_to:
        st.error("⚠️ A data inicial deve ser anterior à data final.")
        st.stop()
    if (date_to - date_from).days > 90:
        st.warning("⚠️ Período longo — pode demorar mais. Recomendado: até 90 dias.")

    _max_lookback = date.today() - timedelta(days=730)
    if date_from < _max_lookback:
        st.warning("⚠️ A Meta limita o histórico a ~2 anos. Dados mais antigos podem estar incompletos.")

    _all_profiles = _load_profiles()
    profile       = _all_profiles[profile_name]
    date_from_str = date_from.isoformat()
    date_to_str   = date_to.isoformat()

    # ── Busca paralela com cache 30 min ──────────────────────────────────────
    with st.spinner(f"⏳ Buscando dados de {profile['handle']} via Meta Graph API…"):
        try:
            fetched = _fetch_all_data(profile["key"], date_from_str, date_to_str, report_type, profile)
        except PermissionError as e:
            st.error(f"🔐 {e}")
            st.stop()
        except ValueError as e:
            st.error(f"❌ {e}")
            st.stop()
        except TimeoutError as e:
            st.error(f"⏱️ {e}")
            st.stop()
        except Exception as e:
            msg = str(e).lower()
            if "connection" in msg or "internet" in msg:
                st.error("🌐 Sem conexão com a API Meta. Verifique sua internet.")
            elif "timeout" in msg or "tempo" in msg:
                st.error("⏱️ A API Meta não respondeu. Tente um período menor.")
            elif "limite" in msg or "429" in msg:
                st.error("⏳ Limite de requisições atingido. Aguarde 1 minuto e tente novamente.")
            else:
                st.error(f"❌ Erro ao buscar dados: {e}")
            st.stop()

    ig_rows      = fetched["ig_rows"]
    profile_info = fetched["profile_info"]
    audience     = fetched["audience"]
    top_posts    = fetched["top_posts"]
    ads_rows     = fetched["ads_rows"]

    if not ig_rows:
        st.warning(
            "⚠️ Nenhum dado de alcance encontrado para o período selecionado. "
            "Tente estender o período ou verifique se há publicações nessas datas."
        )

    if len(top_posts) >= 100:
        st.info("ℹ️ Foram encontrados mais de 100 posts — apenas os 100 mais recentes são analisados no ranking.")

    with st.spinner("🎨 Gerando relatório…"):
        data = process(ig_rows, ads_rows, profile_info, audience, top_posts, date_from_str, date_to_str)

        # Busca comparativo ANTES de gerar o HTML para incluir no relatório
        prev = supabase_db.get_previous_metrics(
            profile["key"], date_from_str, date_to_str, report_type
        )

        # Análise estratégica gerada por IA (rápida, usa Haiku)
        ai_analysis = generate_strategic_analysis(data, profile, report_type)

        # Score de saúde da conta
        health = hs.calculate(data, prev)
        data["health_score"] = health["score"]

        html = generate(
            profile, data, report_type,
            generated_at=datetime.now().strftime("%d/%m/%Y às %H:%M"),
            prev_data=prev,
            ai_analysis=ai_analysis,
            health_score=health,
        )

    st.session_state.report_html   = html
    st.session_state.report_data   = data
    st.session_state.report_label  = f"✅ Relatório gerado — {profile['handle']} · {data['period_label']} · {report_type}"
    st.session_state.report_file   = f"relatorio_{profile['key']}_{date_from_str}_{date_to_str}.html"
    st.session_state.report_config = _current_config
    st.session_state.report_prev   = prev

    # Injeta campos do perfil nos dados antes de salvar no histórico
    data["nicho"]        = profile.get("nicho", "")
    data["sub_nicho"]    = profile.get("sub_nicho", "")
    data["publico_alvo"] = profile.get("publico_alvo", "")

    # Converte ai_analysis para formato seguro (listas em vez de tuplas)
    _ai_safe = None
    if ai_analysis and isinstance(ai_analysis, dict):
        try:
            _ai_safe = {
                "strengths":  [[e, t] for e, t in (ai_analysis.get("strengths") or [])],
                "attentions": [[e, t] for e, t in (ai_analysis.get("attentions") or [])],
            }
        except Exception:
            _ai_safe = None

    # Salva histórico depois (não bloqueia o HTML) — falha aqui não derruba o relatório
    try:
        supabase_db.save_report_metrics(
            profile["key"], date_from_str, date_to_str, report_type, data,
            ai_strategic=_ai_safe,
        )
    except Exception:
        pass  # relatório já foi gerado — save é não-crítico

if not st.session_state.report_html:
    st.markdown("""
    <div class="welcome-card">
        <div style="font-size:3.5rem;margin-bottom:16px;">📊</div>
        <h2 style="color:#003f7c;margin-bottom:8px;font-size:1.4rem;font-weight:700;">Pronto para gerar seu relatório</h2>
        <p style="max-width:420px;line-height:1.7;color:#6b7280;margin:0 auto;">
            Selecione o <strong>perfil</strong>, o <strong>período</strong> e o <strong>tipo de relatório</strong>
            na barra lateral, depois clique em <strong>Gerar Relatório</strong>.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

html = st.session_state.report_html

# ── Render ────────────────────────────────────────────────────────────────────
st.success(st.session_state.report_label)

# ── Trending badges (vs período anterior) ────────────────────────────────────
if st.session_state.report_data and st.session_state.report_prev:
    _badges_html = _trending_badges(st.session_state.report_data, st.session_state.report_prev)
    if _badges_html:
        st.markdown(_badges_html, unsafe_allow_html=True)

# Botão CSV (fora do iframe — download nativo do Streamlit)
if st.session_state.report_data:
    _csv_bytes = _make_csv(st.session_state.report_data).encode("utf-8-sig")  # utf-8-sig = abre certo no Excel
    _csv_name  = st.session_state.report_file.replace(".html", ".csv")
    st.download_button(
        "📊 Baixar dados em CSV",
        data=_csv_bytes,
        file_name=_csv_name,
        mime="text/csv",
        help="Exporta métricas diárias e campanhas em formato CSV (compatível com Excel)",
    )

# ── Barra de ações injetada DENTRO do iframe do relatório ─────────────────────
# Assim não há cross-origin: window.print() e blob URL funcionam diretamente.
_html_b64 = base64.b64encode(html.encode("utf-8")).decode()

_action_bar = (
    '<div id="rpt-actions" style="'
    'position:sticky;top:0;z-index:9999;'
    'background:rgba(255,255,255,0.97);backdrop-filter:blur(8px);'
    'border-bottom:1px solid #dde3ed;padding:10px 20px;'
    'display:flex;gap:10px;align-items:center;'
    "font-family:'Segoe UI',system-ui,sans-serif;\">"
    # Abrir HTML — <a target=_blank> não é bloqueado como popup
    "<a id='btn-open-html' href='#' target='_blank' style='"
    "padding:7px 16px;border:1.5px solid #003f7c;border-radius:7px;"
    "background:#fff;color:#003f7c;font-size:.88rem;font-weight:600;"
    "cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;"
    "align-items:center;'>📂 Abrir HTML</a>"
    # Salvar como PDF
    "<button onclick=\""
    "var el=document.getElementById('rpt-actions');"
    "el.style.display='none';"
    "window.print();"
    "setTimeout(function(){el.style.display='flex';},800);"
    "\" style='"
    "padding:7px 16px;border:none;border-radius:7px;"
    "background:linear-gradient(135deg,#003f7c,#1a5a9a);color:#fff;"
    "font-size:.88rem;font-weight:600;cursor:pointer;font-family:inherit;'>🖨️ Salvar como PDF</button>"
    "</div>"
    # Script: define o href do link com blob URL no carregamento da página
    "<script>"
    "(function(){"
    "var arr=Uint8Array.from(atob('" + _html_b64 + "'),function(c){return c.charCodeAt(0);});"
    "var blob=new Blob([arr],{type:'text/html;charset=utf-8'});"
    "document.getElementById('btn-open-html').href=URL.createObjectURL(blob);"
    "})();"
    "</script>"
)

html_rendered = html.replace("<body>", "<body>" + _action_bar, 1)
components.html(html_rendered, height=5000, scrolling=True)

# ── Histórico de relatórios ───────────────────────────────────────────────────
_profile_key = _load_profiles().get(profile_name, {}).get("key")

if _profile_key:
    _history = supabase_db.get_history_list(_profile_key, limit=12)
    if _history:
        with st.expander("📈 Evolução Histórica — Relatórios Anteriores", expanded=False):
            import pandas as pd

            # Monta DataFrame
            rows_h = []
            for h in reversed(_history):  # cronológico
                m = h.get("metrics", {})
                rows_h.append({
                    "Período":       f"{h['date_from'][5:]}→{h['date_to'][5:]}",
                    "Alcance Total": int(m.get("total_reach", 0)),
                    "Orgânico":      int(m.get("total_organic", 0)),
                    "Interações":    int(m.get("total_interactions", 0)),
                    "Engaj. %":      round(float(m.get("org_eng_rate", 0)), 2),
                    "Seguidores +":  int(m.get("followers_gained", 0)),
                    "Gasto R$":      round(float(m.get("total_spend", 0)), 2),
                    "Tipo":          h.get("report_type", ""),
                })
            df_h = pd.DataFrame(rows_h)

            # Gráfico de linha — Alcance e Interações
            st.markdown("**Alcance Total & Interações por período**")
            st.line_chart(
                df_h.set_index("Período")[["Alcance Total", "Interações"]],
                use_container_width=True,
            )

            # Gráfico de linha — Engajamento orgânico
            st.markdown("**Taxa de Engajamento Orgânico (%)**")
            st.line_chart(
                df_h.set_index("Período")[["Engaj. %"]],
                use_container_width=True,
            )

            # Tabela completa
            st.markdown("**Tabela de todos os períodos**")
            st.dataframe(
                df_h.drop(columns=["Tipo"]),
                use_container_width=True,
                hide_index=True,
            )

st.markdown(
    '<p style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">'
    "Desenvolvido por Dash Digital · @dashdgt · Todos os direitos reservados</p>",
    unsafe_allow_html=True,
)
