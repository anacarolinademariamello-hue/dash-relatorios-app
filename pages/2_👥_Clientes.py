"""
Página de Gerenciamento de Clientes — Dash Digital
Cadastra, edita e desativa clientes no Supabase.
Quando um cliente é salvo aqui, aparece automaticamente
no Gerador de Relatórios e no Gerador de Copies.
"""
import json
import base64
import streamlit as st
import requests

from src import supabase_db

st.set_page_config(
    page_title="Clientes · Dash Digital",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] {background:#0d2137;}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color:#fff !important; }
div[data-testid="stSidebarNav"] { display:none; }
.main .block-container { padding-top:1.5rem; max-width:1000px; }
.client-card {
    background:#fff; border:1px solid #dde3ed; border-radius:14px;
    padding:20px 24px; margin-bottom:14px;
    box-shadow:0 2px 8px rgba(0,0,0,0.05);
    display:flex; align-items:center; gap:18px;
}
.client-avatar {
    font-size:2rem; width:56px; height:56px; border-radius:50%;
    background:#f0f3f8; display:flex; align-items:center;
    justify-content:center; flex-shrink:0;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _logo_b64():
    try:
        with open("assets/logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

def _headers():
    _, key = supabase_db._get_creds()
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }

def _rest(table):
    url, _ = supabase_db._get_creds()
    return f"{url}/rest/v1/{table}"

def load_all_clients():
    """Carrega todos os clientes (ativos e inativos) do Supabase."""
    if not supabase_db.is_configured():
        return []
    try:
        resp = requests.get(
            supabase_db._rest("clients"),
            headers=_headers(),
            params={"order": "name.asc", "select": "*"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []

def save_client(data: dict) -> tuple[bool, str]:
    """Upsert cliente no Supabase."""
    if not supabase_db.is_configured():
        return False, "Supabase não configurado."
    try:
        resp = requests.post(
            supabase_db._rest("clients"),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=data,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True, "✅ Cliente salvo com sucesso!"
        return False, f"Erro {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Erro: {e}"

def toggle_active(key: str, active: bool) -> bool:
    try:
        resp = requests.patch(
            supabase_db._rest("clients"),
            headers=_headers(),
            params={"key": f"eq.{key}"},
            json={"active": active},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    logo = _logo_b64()
    if logo:
        st.markdown(
            f'<div style="padding:12px 4px 8px;">'
            f'<img src="data:image/png;base64,{logo}" style="height:38px;"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 📊 Dash Digital")
    st.markdown("**Gerenciar Clientes**")
    st.markdown("---")
    st.markdown(
        "<small style='opacity:.6;'>Clientes cadastrados aqui aparecem automaticamente no "
        "Gerador de Relatórios e no Gerador de Copies.</small>",
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#003f7c,#1a5a9a);border-radius:16px;
padding:26px 32px;color:#fff;margin-bottom:24px;">
<div style="font-size:1.45rem;font-weight:700;">👥 Gerenciar Clientes</div>
<div style="font-size:.88rem;opacity:.65;margin-top:4px;">
Cadastre e edite os clientes da agência. Alterações aparecem em todas as plataformas.
</div></div>
""", unsafe_allow_html=True)

if not supabase_db.is_configured():
    st.error("⚠️ Supabase não configurado. Verifique `supabase_url` e `supabase_service_key` nos secrets.")
    st.stop()

# ── Session state ─────────────────────────────────────────────────────────────
if "editing_client" not in st.session_state:
    st.session_state.editing_client = None
if "show_new_form" not in st.session_state:
    st.session_state.show_new_form = False

# ── Default colors ────────────────────────────────────────────────────────────
DEFAULT_COLORS = {
    "p": "#003f7c", "p2": "#1a5a9a", "a": "#f8b940", "ad": "#d99a20",
    "al": "rgba(248,185,64,0.13)", "pl": "rgba(0,63,124,0.08)",
    "bg": "#f0f3f8", "header_end": "#2471c8",
    "period_color": "#ffe08a", "stat_color": "#f8b940",
}

# ── Form builder ─────────────────────────────────────────────────────────────
def _client_form(existing: dict = None, form_key: str = "new"):
    """Renderiza formulário de cadastro/edição. Retorna dados ou None."""
    e = existing or {}

    with st.form(key=f"form_{form_key}"):
        st.markdown("##### Dados Básicos")
        col1, col2 = st.columns(2)
        with col1:
            name   = st.text_input("Nome do cliente *", value=e.get("name", ""),
                                   placeholder="Ex: Prof. Wanzeller")
            handle = st.text_input("Handle do Instagram *", value=e.get("handle", ""),
                                   placeholder="Ex: @prof.wanzeller")
            avatar = st.text_input("Emoji / Avatar", value=e.get("avatar", "📊"),
                                   help="Um emoji que representa o cliente")
        with col2:
            key_val = st.text_input(
                "Chave única (slug) *", value=e.get("key", ""),
                placeholder="Ex: wanzeller",
                help="Letras minúsculas, sem espaços, sem acentos. Usado internamente.",
            )
            instagram_id = st.text_input("Instagram ID *", value=e.get("instagram_id", ""),
                                         placeholder="Ex: 17841479657213211")
            facebook_id  = st.text_input("Meta Ads Account ID *", value=e.get("facebook_account_id", ""),
                                         placeholder="Ex: 1429787371828065 (sem act_)")

        bio = st.text_area("Bio / Descrição", value=e.get("bio", ""), height=70,
                           placeholder="Descrição curta do cliente para o cabeçalho do relatório")

        tags_raw = st.text_input(
            "Tags (separadas por vírgula)",
            value=", ".join(e.get("tags", [])),
            placeholder="Ex: #TráfegoPago, #CursosOnline, #Educação",
        )

        footer = st.text_input(
            "Rodapé do relatório",
            value=e.get("footer", ""),
            placeholder="Ex: Relatório gerado para a <strong>Nome</strong> por Dash Digital.",
        )

        st.markdown("##### Tom de Voz (para Gerador de Copies)")
        tone_of_voice = st.text_area(
            "Tom de voz / Guia de comunicação (opcional)",
            value=e.get("tone_of_voice", ""),
            height=90,
            placeholder="Descreva como a marca se comunica: palavras que usa, tom, o que evita...",
        )

        competitors = st.text_input(
            "Páginas concorrentes no Facebook (opcional)",
            value=e.get("competitors", ""),
            placeholder="Ex: Página Concorrente 1, Página Concorrente 2",
        )

        st.markdown("##### Cores do Relatório")
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        colors = e.get("colors") or DEFAULT_COLORS
        if isinstance(colors, str):
            import json as _json
            colors = _json.loads(colors)
        with col_c1:
            p  = st.color_picker("Primária", value=colors.get("p",  "#003f7c"))
            p2 = st.color_picker("Primária 2", value=colors.get("p2", "#1a5a9a"))
        with col_c2:
            a  = st.color_picker("Destaque", value=colors.get("a",  "#f8b940"))
            ad = st.color_picker("Destaque escuro", value=colors.get("ad", "#d99a20"))
        with col_c3:
            header_end   = st.color_picker("Header fim", value=colors.get("header_end",  "#2471c8"))
            period_color = st.color_picker("Período badge", value=colors.get("period_color", "#ffe08a"))
        with col_c4:
            stat_color = st.color_picker("KPI cor", value=colors.get("stat_color", "#f8b940"))

        submitted = st.form_submit_button("💾 Salvar Cliente", use_container_width=True)

    if submitted:
        errors = []
        if not name.strip():    errors.append("Nome é obrigatório.")
        if not handle.strip():  errors.append("Handle é obrigatório.")
        if not key_val.strip(): errors.append("Chave única é obrigatória.")
        if not instagram_id.strip():  errors.append("Instagram ID é obrigatório.")
        if not facebook_id.strip():   errors.append("Meta Ads Account ID é obrigatório.")

        if errors:
            for err in errors:
                st.error(err)
            return None

        def _hex_to_rgba(hex_color, alpha):
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
            return f"rgba({r},{g},{b},{alpha})"

        final_colors = {
            "p": p, "p2": p2, "a": a, "ad": ad,
            "al": _hex_to_rgba(a, 0.13), "pl": _hex_to_rgba(p, 0.08),
            "bg": "#f0f3f8", "header_end": header_end,
            "period_color": period_color, "stat_color": stat_color,
        }

        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        final_footer = footer.strip() or f"Relatório gerado para a <strong>{name.strip()}</strong> por Dash Digital."

        return {
            "key":                 key_val.strip().lower(),
            "name":                name.strip(),
            "handle":              handle.strip(),
            "instagram_id":        instagram_id.strip(),
            "facebook_account_id": facebook_id.strip(),
            "bio":                 bio.strip(),
            "tags":                tags,
            "avatar":              avatar.strip() or "📊",
            "footer":              final_footer,
            "colors":              final_colors,
            "tone_of_voice":       tone_of_voice.strip(),
            "competitors":         competitors.strip(),
            "active":              True,
        }

    return None

# ══════════════════════════════════════════════════════════════════════════════
# LISTA DE CLIENTES
# ══════════════════════════════════════════════════════════════════════════════
clients = load_all_clients()

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown(f"### Clientes cadastrados ({len(clients)})")
with col_btn:
    if st.button("➕ Novo cliente", use_container_width=True):
        st.session_state.show_new_form = True
        st.session_state.editing_client = None

# ── Formulário de novo cliente ────────────────────────────────────────────────
if st.session_state.show_new_form:
    st.markdown("---")
    st.markdown("#### Cadastrar Novo Cliente")
    result = _client_form(form_key="new")
    if result is not None:
        ok, msg = save_client(result)
        if ok:
            st.success(msg)
            st.session_state.show_new_form = False
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(msg)
    if st.button("✕ Cancelar", key="cancel_new"):
        st.session_state.show_new_form = False
        st.rerun()
    st.markdown("---")

# ── Cards de clientes ─────────────────────────────────────────────────────────
if not clients:
    st.info("Nenhum cliente cadastrado ainda. Clique em **➕ Novo cliente** para começar.")
else:
    for client in clients:
        active = client.get("active", True)
        colors = client.get("colors") or {}
        if isinstance(colors, str):
            import json as _json
            colors = _json.loads(colors)
        accent = colors.get("a", "#f8b940")
        opacity = "1.0" if active else "0.45"

        with st.container():
            col_av, col_info, col_actions = st.columns([1, 6, 2])

            with col_av:
                st.markdown(
                    f'<div style="font-size:2rem;width:52px;height:52px;border-radius:50%;'
                    f'background:{accent}22;display:flex;align-items:center;justify-content:center;'
                    f'opacity:{opacity};">{client.get("avatar","📊")}</div>',
                    unsafe_allow_html=True,
                )

            with col_info:
                status_badge = "" if active else ' <span style="background:#fee2e2;color:#991b1b;font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:700;">INATIVO</span>'
                st.markdown(
                    f'<div style="opacity:{opacity};">'
                    f'<strong style="font-size:1rem;color:#003f7c;">{client["name"]}</strong>{status_badge}<br>'
                    f'<span style="font-size:.85rem;color:#6b7280;">{client.get("handle","")}</span> · '
                    f'<span style="font-size:.8rem;color:#9ca3af;">IG: {client.get("instagram_id","")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with col_actions:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✏️", key=f"edit_{client['key']}", help="Editar"):
                        st.session_state.editing_client = client["key"]
                        st.session_state.show_new_form = False
                with btn_col2:
                    if active:
                        if st.button("🔕", key=f"deact_{client['key']}", help="Desativar"):
                            if toggle_active(client["key"], False):
                                st.success(f"'{client['name']}' desativado.")
                                st.cache_data.clear()
                                st.rerun()
                    else:
                        if st.button("✅", key=f"act_{client['key']}", help="Reativar"):
                            if toggle_active(client["key"], True):
                                st.success(f"'{client['name']}' reativado.")
                                st.cache_data.clear()
                                st.rerun()

        # ── Formulário de edição inline ────────────────────────────────────────
        if st.session_state.editing_client == client["key"]:
            with st.expander(f"✏️ Editando: {client['name']}", expanded=True):
                result = _client_form(existing=client, form_key=f"edit_{client['key']}")
                if result is not None:
                    ok, msg = save_client(result)
                    if ok:
                        st.success(msg)
                        st.session_state.editing_client = None
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(msg)
                if st.button("✕ Cancelar edição", key=f"cancel_edit_{client['key']}"):
                    st.session_state.editing_client = None
                    st.rerun()

        st.divider()

st.markdown(
    '<p style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">'
    "Desenvolvido por Dash Digital · @dashdgt · Todos os direitos reservados</p>",
    unsafe_allow_html=True,
)
