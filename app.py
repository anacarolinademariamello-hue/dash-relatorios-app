import base64
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, timedelta, datetime

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

div[data-testid="stSidebarNav"] {display:none;}

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

    # ── Aviso de expiração do token Meta ──────────────────────────────────────
    try:
        token_created_str = st.secrets.get("meta_token_created", "")
        if token_created_str:
            token_created = datetime.strptime(token_created_str, "%Y-%m-%d").date()
            token_expires = token_created + timedelta(days=60)
            days_left = (token_expires - date.today()).days
            if days_left <= 0:
                st.markdown(
                    "<div style='background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;"
                    "padding:10px 12px;font-size:.78rem;color:#991b1b;margin-bottom:8px;'>"
                    "🔴 <strong>Token Meta expirado!</strong><br>Renove o token para gerar relatórios.</div>",
                    unsafe_allow_html=True,
                )
            elif days_left <= 10:
                st.markdown(
                    f"<div style='background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;"
                    f"padding:10px 12px;font-size:.78rem;color:#92400e;margin-bottom:8px;'>"
                    f"⚠️ <strong>Token expira em {days_left} dias</strong><br>"
                    f"Renove antes de {token_expires.strftime('%d/%m/%Y')}.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<small style='opacity:.45;font-size:.7rem;'>🔑 Token válido por mais {days_left} dias</small>",
                    unsafe_allow_html=True,
                )
    except Exception:
        pass

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

# ── Session state para persistir relatório ────────────────────────────────────
if "report_html"  not in st.session_state: st.session_state.report_html  = None
if "report_label" not in st.session_state: st.session_state.report_label = ""
if "report_file"  not in st.session_state: st.session_state.report_file  = ""

if gerar:
    # ── Validate ─────────────────────────────────────────────────────────────
    if date_from > date_to:
        st.error("⚠️ A data inicial deve ser anterior à data final.")
        st.stop()
    if (date_to - date_from).days > 90:
        st.warning("⚠️ Período muito longo pode demorar. Recomendado: até 90 dias.")

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
            st.info("Verifique se o token Meta está configurado corretamente.")
            st.stop()

    if not ig_rows:
        st.warning("⚠️ Nenhum dado de alcance encontrado para o período selecionado.")

    with st.spinner("🎨 Gerando relatório..."):
        data = process(ig_rows, ads_rows, profile_info, audience, top_posts, date_from_str, date_to_str)
        html = generate(profile, data, report_type)

    st.session_state.report_html  = html
    st.session_state.report_label = f"✅ Relatório gerado — {profile['handle']} · {data['period_label']} · {report_type}"
    st.session_state.report_file  = f"relatorio_{profile['key']}_{date_from_str}_{date_to_str}.html"

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

# Botões de ação
_html_b64 = base64.b64encode(html.encode("utf-8")).decode()
col_dl, col_pdf, _ = st.columns([1, 1, 2])

# ── Botão "Abrir HTML" — abre nova aba via blob URL (dentro de components.html
#    para evitar restrições do sandbox do Streamlit)
with col_dl:
    components.html(f"""
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
button{{
  width:100%;height:40px;
  background:#fff;color:#003f7c;
  border:1.5px solid #003f7c;border-radius:8px;
  font-size:.88rem;font-weight:600;cursor:pointer;
  font-family:'Segoe UI',system-ui,sans-serif;
  transition:background .15s;
}}
button:hover{{background:#e8f0fb;}}
</style>
<button onclick="
  var b=atob('{_html_b64}');
  var blob=new Blob([b],{{type:'text/html;charset=utf-8'}});
  window.open(URL.createObjectURL(blob),'_blank');
">📂 Abrir HTML</button>
""", height=46)

# ── Botão "Salvar como PDF" — chama print() diretamente no iframe do relatório
with col_pdf:
    st.markdown("""
<style>
.btn-pdf-wrap > button {
    width:100%;padding:.45rem .9rem;
    background:linear-gradient(135deg,#003f7c,#1a5a9a)!important;
    color:#fff!important;border:none!important;border-radius:.5rem!important;
    font-size:.9rem!important;font-weight:600!important;cursor:pointer;
    transition:all .2s;line-height:1.6;
}
.btn-pdf-wrap > button:hover {
    background:linear-gradient(135deg,#1a5a9a,#2468b0)!important;
    transform:translateY(-1px);
}
</style>
<div class="btn-pdf-wrap">
<button onclick="
  var frames = document.querySelectorAll('iframe');
  var ok = false;
  for(var i=0;i<frames.length;i++){
    try{
      var d = frames[i].contentDocument;
      if(d && d.querySelector('.site-header')){
        frames[i].contentWindow.print();
        ok=true; break;
      }
    }catch(e){}
  }
  if(!ok) alert('Aguarde o relatório carregar e tente novamente.');
">🖨️ Salvar como PDF</button>
</div>
""", unsafe_allow_html=True)

components.html(html, height=5000, scrolling=True)

st.markdown(
    '<p style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">'
    "Desenvolvido por Dash Digital · @dashdgt · Todos os direitos reservados</p>",
    unsafe_allow_html=True,
)
