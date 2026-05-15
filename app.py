import streamlit as st
import streamlit.components.v1 as components
from datetime import date, timedelta

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

div[data-testid="stSidebarNav"] {display:none;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Dash Digital")
    st.markdown("**Gerador de Relatórios**")
    st.markdown("---")

    profile_name = st.selectbox(
        "Perfil",
        list(PROFILES.keys()),
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

    gerar = st.button("🚀 Gerar Relatório", use_container_width=True)

    st.markdown("---")
    st.markdown(
        "<small style='opacity:.55'>Os dados são buscados em tempo real<br>via Instagram Insights + Meta Ads</small>",
        unsafe_allow_html=True,
    )

# ── Main area ─────────────────────────────────────────────────────────────────
if not gerar:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                padding:80px 20px;color:#6b7280;text-align:center;">
        <div style="font-size:4rem;margin-bottom:16px;">📊</div>
        <h2 style="color:#003f7c;margin-bottom:8px;">Gerador de Relatórios</h2>
        <p style="max-width:400px;line-height:1.6;">
            Selecione o perfil, o período e o tipo de relatório na barra lateral,
            depois clique em <strong>Gerar Relatório</strong>.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Validate ─────────────────────────────────────────────────────────────────
if date_from > date_to:
    st.error("⚠️ A data inicial deve ser anterior à data final.")
    st.stop()

if (date_to - date_from).days > 90:
    st.warning("⚠️ Período muito longo pode demorar. Recomendado: até 90 dias.")

# ── Fetch & process ──────────────────────────────────────────────────────────
profile       = PROFILES[profile_name]
date_from_str = date_from.isoformat()
date_to_str   = date_to.isoformat()

with st.spinner(f"⏳ Buscando dados de {profile['handle']}..."):
    try:
        ig_rows      = fetch_instagram_daily(profile, date_from_str, date_to_str)
        profile_info = fetch_instagram_profile(profile)
        audience     = fetch_instagram_audience(profile)
        top_posts    = fetch_instagram_top_posts(profile, date_from_str, date_to_str)
        ads_rows     = fetch_meta_ads_daily(profile, date_from_str, date_to_str) \
                       if report_type != "Só Orgânico" else []
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados: {e}")
        st.info("Verifique se o token Meta está configurado corretamente em `.streamlit/secrets.toml` (campo `meta_access_token`).")
        st.stop()

# Aviso se não houver dados de alcance (período muito antigo ou sem atividade)
if not ig_rows:
    st.warning(
        "⚠️ Nenhum dado de alcance encontrado para o período selecionado. "
        "O Instagram Insights pode não ter dados para períodos muito antigos "
        "ou para contas sem atividade neste intervalo. O relatório será gerado com os dados disponíveis."
    )

with st.spinner("🎨 Gerando relatório..."):
    data = process(ig_rows, ads_rows, profile_info, audience, top_posts, date_from_str, date_to_str)
    html = generate(profile, data, report_type)

# ── Render ────────────────────────────────────────────────────────────────────
st.success(f"✅ Relatório gerado — {profile['handle']} · {data['period_label']} · {report_type}")

# Download button
col_dl, _ = st.columns([1, 4])
with col_dl:
    filename = f"relatorio_{profile['key']}_{date_from_str}_{date_to_str}.html"
    st.download_button(
        "⬇ Baixar HTML",
        data=html.encode("utf-8"),
        file_name=filename,
        mime="text/html",
        use_container_width=True,
    )

components.html(html, height=5000, scrolling=True)
