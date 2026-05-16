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
from src import supabase_db


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_all_data(profile_key: str, date_from: str, date_to: str, report_type: str) -> dict:
    """
    Busca todos os dados Meta em paralelo (5 requisições simultâneas).
    Resultado em cache por 30 min — nova geração para o mesmo período
    é instantânea até o token expirar ou o TTL vencer.
    """
    profile = PROFILES[profile_key]

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
        "Interações Totais", "Seguidores Ganhos",
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

# ── View (query param) — definido antes do sidebar ───────────────────────────
_view = st.query_params.get("view", "")

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

    if _view == "clientes":
        # ── Sidebar da vista Gerenciar Clientes ───────────────────────────────
        st.markdown("**👥 Gerenciar Clientes**")
        st.markdown(
            '<a href="/" target="_self" style="display:block;color:rgba(255,255,255,0.70);'
            'text-decoration:none;font-size:.85rem;padding:4px 0 8px 0;">'
            '← Voltar ao Gerador de Relatórios</a>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown(
            "<small style='opacity:.55;font-size:.78rem;'>Clientes cadastrados aqui aparecem "
            "automaticamente no Gerador de Relatórios e no Gerador de Copies.</small>",
            unsafe_allow_html=True,
        )
        # Variáveis dummy (não usadas na vista clientes)
        profile_name = None
        gerar        = False
        date_from = date_to = report_type = None
    else:
        # ── Sidebar do Gerador de Relatórios ──────────────────────────────────
        st.markdown("**Gerador de Relatórios**")
        st.markdown(
            '<a href="/?view=clientes" target="_self" style="display:block;'
            'color:rgba(255,255,255,0.75);text-decoration:none;font-size:.87rem;'
            'padding:4px 0 8px 0;">👥 Gerenciar Clientes</a>',
            unsafe_allow_html=True,
        )
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

# ── Vista: Gerenciar Clientes (?view=clientes) ────────────────────────────────
if _view == "clientes":
    import json as _cljson

    # ── Helpers REST ──────────────────────────────────────────────────────────
    def _cl_headers():
        _, key = supabase_db._get_creds()
        return {"apikey": key, "Authorization": f"Bearer {key}",
                "Content-Type": "application/json", "Prefer": "return=representation"}

    def _cl_rest(table):
        url, _ = supabase_db._get_creds()
        return f"{url}/rest/v1/{table}"

    def _extract_file(f):
        try:
            name = f.name.lower()
            if name.endswith(".pdf"):
                import pypdf
                reader = pypdf.PdfReader(f)
                return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
            return f.read().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            return f"[Erro ao ler arquivo: {e}]"

    @st.cache_data(ttl=60)
    def _load_all_clients():
        if not supabase_db.is_configured():
            return []
        try:
            r = requests.get(_cl_rest("clients"), headers=_cl_headers(),
                             params={"order": "name.asc", "select": "*"}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def _save_client(data):
        if not supabase_db.is_configured():
            return False, "Supabase não configurado."
        try:
            r = requests.post(
                _cl_rest("clients"),
                headers={**_cl_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=data, timeout=10,
            )
            if r.status_code in (200, 201):
                return True, "✅ Cliente salvo com sucesso!"
            return False, f"Erro {r.status_code}: {r.text}"
        except Exception as e:
            return False, f"Erro: {e}"

    def _toggle_active(key, active):
        try:
            r = requests.patch(_cl_rest("clients"), headers=_cl_headers(),
                               params={"key": f"eq.{key}"}, json={"active": active}, timeout=10)
            return r.status_code in (200, 204)
        except Exception:
            return False

    _CL_DEFAULT_COLORS = {
        "p": "#003f7c", "p2": "#1a5a9a", "a": "#f8b940", "ad": "#d99a20",
        "header_end": "#2471c8", "period_color": "#ffe08a", "stat_color": "#f8b940",
    }

    def _rgba(h, alpha):
        h = h.lstrip("#")
        try:
            r2, g2, b2 = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r2},{g2},{b2},{alpha})"
        except Exception:
            return f"rgba(0,63,124,{alpha})"

    def _client_form(existing=None, form_key="new"):
        e = existing or {}
        colors = e.get("colors") or _CL_DEFAULT_COLORS
        if isinstance(colors, str):
            colors = _cljson.loads(colors)
        goals = e.get("goals") or {}
        if isinstance(goals, str):
            goals = _cljson.loads(goals)

        with st.form(key=f"clform_{form_key}"):

            # ── 1. Identificação ───────────────────────────────────────────────
            st.markdown("#### 👤 Identificação")
            ci1, ci2 = st.columns(2)
            with ci1:
                name   = st.text_input("Nome do cliente *",
                                        value=e.get("name", ""),
                                        placeholder="Ex: Prof. Wanzeller")
                handle = st.text_input("Handle do Instagram *",
                                        value=e.get("handle", ""),
                                        placeholder="Ex: @prof.wanzeller")
            with ci2:
                slug = st.text_input(
                    "Identificador interno (slug) *",
                    value=e.get("key", ""),
                    placeholder="Ex: wanzeller",
                    help="Texto curto sem espaços ou acentos, em letras minúsculas. "
                         "Usado para identificar o cliente no sistema.",
                )
                avatar = st.text_input("Emoji do cliente",
                                        value=e.get("avatar", "📊"),
                                        help="Um emoji representativo do cliente. Ex: 🎓 👩‍💼 📚")

            st.divider()

            # ── 2. IDs das contas Meta ─────────────────────────────────────────
            st.markdown("#### 📱 IDs das Contas Meta")
            st.caption(
                "Os IDs são necessários para buscar os dados da conta na API da Meta. "
                "**Instagram Business ID:** Meta Business Suite → Configurações → Contas do Instagram → selecione a conta → ID. "
                "**Meta Ads ID:** Gerenciador de Anúncios → a URL mostra 'act_NÚMERO' — use só o número."
            )
            cm1, cm2 = st.columns(2)
            with cm1:
                ig_id = st.text_input("ID da Conta Instagram Business *",
                                       value=e.get("instagram_id", ""),
                                       placeholder="Ex: 17841479657213211")
            with cm2:
                fb_id = st.text_input("ID da Conta Meta Ads *",
                                       value=e.get("facebook_account_id", ""),
                                       placeholder="Ex: 1429787371828065  (sem o act_)")

            st.divider()

            # ── 3. Apresentação no Relatório ──────────────────────────────────
            st.markdown("#### 📄 Apresentação no Relatório")
            bio = st.text_area(
                "Descrição do cliente",
                value=e.get("bio", ""),
                height=75,
                placeholder="Aparece no cabeçalho do relatório. Ex: 'Professor de matemática para concursos públicos'",
                help="Preenchida manualmente — a bio real do Instagram pode ser diferente do que você quer exibir no relatório.",
            )
            hashtags = st.text_input(
                "Hashtags / Áreas de atuação",
                value=", ".join(e.get("tags") or []),
                placeholder="Ex: #Educação, #ConcursoPúblico, #TráfegoPago",
                help="Aparecem como etiquetas no cabeçalho do relatório, identificando as áreas de atuação do cliente. "
                     "Separe por vírgula.",
            )
            footer = st.text_input(
                "Rodapé do relatório",
                value=e.get("footer", ""),
                placeholder="Se vazio, será gerado automaticamente com o nome do cliente.",
            )

            st.divider()

            # ── 4. Tom de Voz ─────────────────────────────────────────────────
            st.markdown("#### 🗣️ Tom de Voz")
            st.caption("Usado pelo Gerador de Copies para criar textos alinhados com a comunicação do cliente.")
            tv1, tv2 = st.columns(2)
            with tv1:
                tov_file = st.file_uploader(
                    "Upload do guia de tom de voz (TXT ou PDF)",
                    type=["txt", "pdf"],
                    key=f"tov_file_{form_key}",
                    help="Se fizer upload, o conteúdo do arquivo substitui o texto digitado abaixo.",
                )
            with tv2:
                tov_text = st.text_area(
                    "Ou descreva o tom de voz",
                    value=e.get("tone_of_voice", ""),
                    height=120,
                    placeholder="Como o cliente fala? Que palavras usa? O que evita? Qual é o tom? Exemplos de frases...",
                )
            competitors = st.text_input(
                "Páginas concorrentes no Facebook",
                value=e.get("competitors", ""),
                placeholder="Ex: Página Concorrente A, Página Concorrente B",
                help="Usado para análise competitiva no Gerador de Copies.",
            )

            st.divider()

            # ── 5. Cores do Relatório ─────────────────────────────────────────
            st.markdown("#### 🎨 Cores do Relatório")
            st.caption("Cole o código hex de cada cor (formato #RRGGBB). Ao salvar, as cores são aplicadas ao relatório.")
            _color_defs = [
                ("p",            "Cor primária",               colors.get("p",            "#003f7c")),
                ("p2",           "Cor primária secundária",     colors.get("p2",           "#1a5a9a")),
                ("a",            "Cor de destaque",             colors.get("a",            "#f8b940")),
                ("ad",           "Destaque escuro",             colors.get("ad",           "#d99a20")),
                ("header_end",   "Cor final do cabeçalho",      colors.get("header_end",   "#2471c8")),
                ("period_color", "Cor do badge de período",     colors.get("period_color", "#ffe08a")),
                ("stat_color",   "Cor dos números (KPIs)",      colors.get("stat_color",   "#f8b940")),
            ]
            _col_vals = {}
            for i in range(0, len(_color_defs), 2):
                row = st.columns([5, 1, 5, 1])
                for j in range(2):
                    if i + j < len(_color_defs):
                        fk, lbl, dflt = _color_defs[i + j]
                        with row[j * 2]:
                            val = st.text_input(lbl, value=dflt,
                                                key=f"col_{fk}_{form_key}", max_chars=7)
                            _col_vals[fk] = val
                        with row[j * 2 + 1]:
                            st.markdown(
                                f'<div style="margin-top:28px;width:34px;height:34px;'
                                f'border-radius:6px;background:{dflt};'
                                f'border:1px solid #dde3ed;"></div>',
                                unsafe_allow_html=True,
                            )

            st.divider()

            # ── 6. Metas de Tráfego Pago ──────────────────────────────────────
            st.markdown("#### 🎯 Metas de Tráfego Pago")
            st.caption(
                "Defina os limites e objetivos para cada métrica. "
                "Esses valores são usados nos alertas automáticos e na análise de performance. "
                "Deixe em 0 (zero) para não definir uma meta."
            )
            mg1, mg2, mg3 = st.columns(3)
            with mg1:
                st.markdown("**Aquisição de Seguidores**")
                g_seg = st.number_input("Custo máx. por seguidor (R$)",
                                         min_value=0.0, step=0.50, format="%.2f",
                                         value=float(goals.get("custo_por_seguidor") or 0))
                g_cpm = st.number_input("CPM máximo — custo por mil impressões (R$)",
                                         min_value=0.0, step=1.0, format="%.2f",
                                         value=float(goals.get("cpm_maximo") or 0))
            with mg2:
                st.markdown("**Vendas / Conversões**")
                g_venda = st.number_input("Custo máx. por venda (R$)",
                                           min_value=0.0, step=1.0, format="%.2f",
                                           value=float(goals.get("custo_por_venda") or 0))
                g_cpa = st.number_input("CPA máximo — custo por resultado (R$)",
                                         min_value=0.0, step=1.0, format="%.2f",
                                         value=float(goals.get("cpa_maximo") or 0))
                g_roas = st.number_input("ROAS mínimo (×) — retorno sobre investimento",
                                          min_value=0.0, step=0.5, format="%.1f",
                                          value=float(goals.get("roas_minimo") or 0))
            with mg3:
                st.markdown("**Engajamento / Cliques**")
                g_ctr = st.number_input("CTR mínimo (%)",
                                         min_value=0.0, step=0.1, format="%.2f",
                                         value=float(goals.get("ctr_minimo") or 0))
                g_cpc = st.number_input("CPC máximo — custo por clique (R$)",
                                         min_value=0.0, step=0.10, format="%.2f",
                                         value=float(goals.get("cpc_maximo") or 0))
                g_conv = st.number_input("Taxa de conversão mínima (%)",
                                          min_value=0.0, step=0.1, format="%.2f",
                                          value=float(goals.get("taxa_conversao_minima") or 0))

            st.divider()

            # ── 7. Observações ────────────────────────────────────────────────
            st.markdown("#### 📝 Observações")
            observations = st.text_area(
                "Observações sobre o cliente",
                value=e.get("observations", ""),
                height=100,
                placeholder="Informações importantes, particularidades da conta, contexto, acordos comerciais, etc.",
                label_visibility="collapsed",
            )

            submitted = st.form_submit_button("💾 Salvar Cliente", use_container_width=True, type="primary")

        if not submitted:
            return None

        # ── Validação ─────────────────────────────────────────────────────────
        errs = []
        if not name.strip():   errs.append("Nome do cliente")
        if not handle.strip(): errs.append("Handle do Instagram")
        if not slug.strip():   errs.append("Identificador interno")
        if not ig_id.strip():  errs.append("ID da Conta Instagram")
        if not fb_id.strip():  errs.append("ID da Conta Meta Ads")
        if errs:
            st.error(f"Campos obrigatórios não preenchidos: **{', '.join(errs)}**")
            return None

        # ── Tom de voz (arquivo tem prioridade) ───────────────────────────────
        tov_final = tov_text.strip()
        if tov_file is not None:
            tov_final = _extract_file(tov_file)

        # ── Cores finais ──────────────────────────────────────────────────────
        p_v  = _col_vals.get("p",  "#003f7c")
        a_v  = _col_vals.get("a",  "#f8b940")
        final_colors = {
            "p":            p_v,
            "p2":           _col_vals.get("p2",  "#1a5a9a"),
            "a":            a_v,
            "ad":           _col_vals.get("ad",  "#d99a20"),
            "al":           _rgba(a_v,  0.13),
            "pl":           _rgba(p_v,  0.08),
            "bg":           "#f0f3f8",
            "header_end":   _col_vals.get("header_end",   "#2471c8"),
            "period_color": _col_vals.get("period_color", "#ffe08a"),
            "stat_color":   _col_vals.get("stat_color",   "#f8b940"),
        }

        # ── Metas ─────────────────────────────────────────────────────────────
        def _g(v): return v if v and v > 0 else None
        final_goals = {k: v for k, v in {
            "custo_por_seguidor":    _g(g_seg),
            "custo_por_venda":       _g(g_venda),
            "cpa_maximo":            _g(g_cpa),
            "ctr_minimo":            _g(g_ctr),
            "cpm_maximo":            _g(g_cpm),
            "cpc_maximo":            _g(g_cpc),
            "roas_minimo":           _g(g_roas),
            "taxa_conversao_minima": _g(g_conv),
        }.items() if v is not None}

        return {
            "key":                 slug.strip().lower().replace(" ", "-"),
            "name":                name.strip(),
            "handle":              handle.strip(),
            "instagram_id":        ig_id.strip(),
            "facebook_account_id": fb_id.strip(),
            "bio":                 bio.strip(),
            "tags":                [t.strip() for t in hashtags.split(",") if t.strip()],
            "avatar":              avatar.strip() or "📊",
            "footer":              footer.strip() or f"Relatório gerado para <strong>{name.strip()}</strong> por Dash Digital.",
            "colors":              final_colors,
            "tone_of_voice":       tov_final,
            "competitors":         competitors.strip(),
            "goals":               final_goals,
            "observations":        observations.strip(),
            "active":              True,
        }

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);border-radius:16px;
    padding:26px 32px;color:#fff;margin-bottom:24px;">
    <div style="font-size:1.45rem;font-weight:700;">👥 Gerenciar Clientes</div>
    <div style="font-size:.88rem;opacity:.65;margin-top:4px;">
    Cadastre, edite e gerencie os clientes da agência.
    Alterações aparecem automaticamente no Gerador de Relatórios e no Gerador de Copies.
    </div></div>
    """, unsafe_allow_html=True)

    if not supabase_db.is_configured():
        st.error("⚠️ Supabase não configurado. Verifique `supabase_url` e `supabase_service_key` nos Secrets do Streamlit Cloud.")
        st.stop()

    # ── Session state ─────────────────────────────────────────────────────────
    for _k, _v in [("cl_editing", None), ("cl_new", False)]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # ── Lista de clientes ─────────────────────────────────────────────────────
    clients_list = _load_all_clients()
    col_t, col_b = st.columns([4, 1])
    with col_t:
        st.markdown(f"### Clientes cadastrados ({len(clients_list)})")
    with col_b:
        if st.button("➕ Novo cliente", use_container_width=True):
            st.session_state.cl_new = True
            st.session_state.cl_editing = None

    # ── Formulário novo cliente ───────────────────────────────────────────────
    if st.session_state.cl_new:
        with st.expander("➕ Cadastrar Novo Cliente", expanded=True):
            result = _client_form(form_key="new")
            if result is not None:
                ok, msg = _save_client(result)
                if ok:
                    st.success(msg)
                    st.session_state.cl_new = False
                    _load_all_clients.clear()
                    st.rerun()
                else:
                    st.error(msg)
            if st.button("✕ Cancelar", key="cl_cancel_new"):
                st.session_state.cl_new = False
                st.rerun()

    # ── Cards dos clientes ────────────────────────────────────────────────────
    if not clients_list:
        st.info("Nenhum cliente cadastrado ainda. Clique em **➕ Novo cliente** para começar.")
    else:
        for cl in clients_list:
            active  = cl.get("active", True)
            colors  = cl.get("colors") or {}
            if isinstance(colors, str):
                colors = _cljson.loads(colors)
            accent  = colors.get("a", "#f8b940")
            opacity = "1.0" if active else "0.45"

            cav, cinf, cact = st.columns([1, 7, 2])
            with cav:
                st.markdown(
                    f'<div style="font-size:2rem;width:52px;height:52px;border-radius:50%;'
                    f'background:{accent}22;display:flex;align-items:center;'
                    f'justify-content:center;opacity:{opacity};">{cl.get("avatar","📊")}</div>',
                    unsafe_allow_html=True,
                )
            with cinf:
                badge = (
                    "" if active else
                    ' <span style="background:#fee2e2;color:#991b1b;font-size:.7rem;'
                    'padding:2px 8px;border-radius:10px;font-weight:700;">INATIVO</span>'
                )
                has_goals = bool(cl.get("goals"))
                has_tov   = bool(cl.get("tone_of_voice", "").strip())
                extras = " · ".join(filter(None, [
                    "🎯 Metas" if has_goals else "",
                    "🗣️ Tom de voz" if has_tov else "",
                ]))
                st.markdown(
                    f'<div style="opacity:{opacity};">'
                    f'<strong style="font-size:1rem;color:#003f7c;">{cl["name"]}</strong>{badge}<br>'
                    f'<span style="font-size:.85rem;color:#6b7280;">{cl.get("handle","")} · '
                    f'IG: {cl.get("instagram_id","")}</span>'
                    + (f'<br><span style="font-size:.78rem;color:#9ca3af;">{extras}</span>' if extras else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )
            with cact:
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✏️", key=f"cl_ed_{cl['key']}", help="Editar"):
                        st.session_state.cl_editing = cl["key"]
                        st.session_state.cl_new = False
                with b2:
                    if active:
                        if st.button("🔕", key=f"cl_da_{cl['key']}", help="Desativar"):
                            if _toggle_active(cl["key"], False):
                                _load_all_clients.clear(); st.rerun()
                    else:
                        if st.button("✅", key=f"cl_ac_{cl['key']}", help="Reativar"):
                            if _toggle_active(cl["key"], True):
                                _load_all_clients.clear(); st.rerun()

            if st.session_state.cl_editing == cl["key"]:
                with st.expander(f"✏️ Editando: {cl['name']}", expanded=True):
                    result = _client_form(existing=cl, form_key=f"edit_{cl['key']}")
                    if result is not None:
                        ok, msg = _save_client(result)
                        if ok:
                            st.success(msg)
                            st.session_state.cl_editing = None
                            _load_all_clients.clear(); st.rerun()
                        else:
                            st.error(msg)
                    if st.button("✕ Cancelar edição", key=f"cl_ce_{cl['key']}"):
                        st.session_state.cl_editing = None; st.rerun()

            st.divider()

    st.stop()

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
            fetched = _fetch_all_data(profile["key"], date_from_str, date_to_str, report_type)
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
        html = generate(
            profile, data, report_type,
            generated_at=datetime.now().strftime("%d/%m/%Y às %H:%M"),
        )

    st.session_state.report_html   = html
    st.session_state.report_data   = data
    st.session_state.report_label  = f"✅ Relatório gerado — {profile['handle']} · {data['period_label']} · {report_type}"
    st.session_state.report_file   = f"relatorio_{profile['key']}_{date_from_str}_{date_to_str}.html"
    st.session_state.report_config = _current_config

    # ── Salvar histórico + buscar comparativo ─────────────────────────────────
    supabase_db.save_report_metrics(
        profile["key"], date_from_str, date_to_str, report_type, data
    )
    prev = supabase_db.get_previous_metrics(
        profile["key"], date_from_str, date_to_str, report_type
    )
    st.session_state.report_prev = prev  # None if no history yet

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

st.markdown(
    '<p style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">'
    "Desenvolvido por Dash Digital · @dashdgt · Todos os direitos reservados</p>",
    unsafe_allow_html=True,
)
