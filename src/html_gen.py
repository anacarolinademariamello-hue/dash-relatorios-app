"""
Generates the full HTML analytics report from processed data + profile config.
report_type: "Geral" | "Só Orgânico" | "Só Pago"
"""
import json


# ── Helpers ───────────────────────────────────────────────────────────────────

def _br(v, decimals=0):
    """Format number Brazilian style."""
    if decimals:
        s = f"{v:,.{decimals}f}"
    else:
        s = f"{int(round(v)):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _js(arr):
    return json.dumps(arr)


def _status_pill(status):
    mapping = {
        "best":    ('<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
                    'font-size:0.75rem;font-weight:700;background:#dcfce7;color:#14532d">🏆 Melhor</span>'),
        "ok":      ('<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
                    'font-size:0.75rem;font-weight:700;background:#d1fae5;color:#065f46">✅ Bom</span>'),
        "warning": ('<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
                    'font-size:0.75rem;font-weight:700;background:#fef3c7;color:#b45309">⚠️ Revisar</span>'),
        "ended":   ('<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
                    'font-size:0.75rem;font-weight:700;background:#f3f4f6;color:#6b7280">🔚 Encerrada</span>'),
    }
    return mapping.get(status, "")


def _format_icon(fmt):
    return {"Reel": "🎬", "Carrossel": "🔄", "Foto": "📸", "Vídeo": "▶️"}.get(fmt, "📄")


# ── CSS ───────────────────────────────────────────────────────────────────────

def _css(c: dict) -> str:
    return f"""<style>
:root{{--p:{c['p']};--p2:{c['p2']};--a:{c['a']};--ad:{c['ad']};--al:{c['al']};--pl:{c['pl']};--bg:{c['bg']};--white:#fff;--text:#1a1a2e;--muted:#6b7280;--border:#dde3ed;--green:#10b981;--orange:#f97316;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;font-size:15px;}}
a{{color:var(--p2);text-decoration:none;}}a:hover{{text-decoration:underline;}}
.site-header{{background:linear-gradient(135deg,var(--p) 0%,var(--p2) 60%,{c['header_end']} 100%);color:#fff;padding:48px 24px 40px;text-align:center;position:relative;overflow:hidden;}}
.site-header::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 80% 20%,rgba(255,255,255,0.10) 0%,transparent 60%);pointer-events:none;}}
.avatar-wrap{{width:90px;height:90px;border-radius:50%;background:linear-gradient(135deg,var(--a),var(--ad));display:flex;align-items:center;justify-content:center;font-size:2.4rem;margin:0 auto 16px;box-shadow:0 4px 20px rgba(0,0,0,0.3);border:3px solid rgba(255,255,255,0.3);overflow:hidden;}}
.header-handle{{font-size:1rem;opacity:0.8;letter-spacing:0.05em;margin-bottom:4px;}}
.header-name{{font-size:2rem;font-weight:700;letter-spacing:-0.02em;margin-bottom:10px;}}
.header-bio{{max-width:520px;margin:0 auto 16px;opacity:0.88;font-size:0.95rem;line-height:1.5;}}
.header-tags{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:24px;}}
.htag{{background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);border-radius:20px;padding:4px 14px;font-size:0.8rem;}}
.header-stats{{display:flex;justify-content:center;gap:32px;margin-bottom:24px;flex-wrap:wrap;}}
.hstat{{text-align:center;}}.hstat-val{{font-size:1.5rem;font-weight:700;color:{c['stat_color']};}}
.hstat-lbl{{font-size:0.78rem;opacity:0.75;text-transform:uppercase;letter-spacing:0.06em;}}
.period-badge{{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.30);border-radius:24px;padding:8px 20px;font-size:0.88rem;color:{c['period_color']};font-weight:600;}}
.container{{max-width:1100px;margin:0 auto;padding:0 20px;}}
.section{{padding:40px 0 8px;}}
.section-title{{font-size:1.35rem;font-weight:700;color:var(--p);border-left:4px solid var(--a);padding-left:14px;margin-bottom:24px;}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:24px;}}
.kpi-card{{background:var(--white);border-radius:14px;padding:20px 18px;border:1px solid var(--border);box-shadow:0 2px 8px rgba(0,0,0,0.06);position:relative;overflow:hidden;transition:transform .15s;}}
.kpi-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--p),var(--a));}}
.kpi-card:hover{{transform:translateY(-3px);}}
.kpi-icon{{font-size:1.6rem;margin-bottom:8px;display:block;}}
.kpi-val{{font-size:1.6rem;font-weight:700;color:var(--p);line-height:1;margin-bottom:4px;}}
.kpi-label{{font-size:0.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;}}
.kpi-badge{{display:inline-block;font-size:0.72rem;padding:2px 8px;border-radius:10px;margin-top:6px;font-weight:600;}}
.badge-green{{background:#d1fae5;color:#065f46;}}.badge-blue{{background:var(--pl);color:var(--p);}}.badge-gold{{background:var(--al);color:var(--ad);}}.badge-orange{{background:#fff7ed;color:#c2410c;}}
.obs-card{{background:linear-gradient(135deg,var(--al),rgba(255,255,255,0.9));border:1.5px solid var(--a);border-radius:14px;padding:24px 28px;margin-bottom:32px;}}
.obs-card h3{{color:var(--p);font-size:1.05rem;margin-bottom:10px;}}.obs-card p{{color:#374151;font-size:0.92rem;line-height:1.7;}}
.chart-row{{display:grid;gap:20px;margin-bottom:24px;}}
.chart-row.cols-1{{grid-template-columns:1fr;}}.chart-row.cols-2{{grid-template-columns:1fr 1fr;}}.chart-row.cols-3{{grid-template-columns:repeat(3,1fr);}}
.chart-card{{background:var(--white);border-radius:14px;padding:24px;border:1px solid var(--border);box-shadow:0 2px 8px rgba(0,0,0,0.06);}}
.chart-card h4{{font-size:0.92rem;font-weight:700;color:var(--p);margin-bottom:16px;text-transform:uppercase;letter-spacing:0.05em;}}
.mini-kpi-row{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:24px;}}
.mini-kpi{{background:var(--white);border:1px solid var(--border);border-radius:10px;padding:14px 16px;text-align:center;}}
.mini-kpi .val{{font-size:1.2rem;font-weight:700;color:var(--p);}}.mini-kpi .lbl{{font-size:0.75rem;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:0.04em;}}
.table-wrap{{background:var(--white);border-radius:14px;border:1px solid var(--border);overflow:hidden;overflow-x:auto;margin-bottom:24px;}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem;}}
thead tr{{background:linear-gradient(90deg,var(--p),var(--p2));color:#fff;}}
thead th{{padding:12px 16px;text-align:left;font-weight:600;font-size:0.8rem;letter-spacing:0.04em;text-transform:uppercase;white-space:nowrap;}}
tbody tr{{border-bottom:1px solid var(--border);}}tbody tr:last-child{{border-bottom:none;}}tbody tr:hover{{background:var(--pl);}}
tbody td{{padding:12px 16px;color:#374151;white-space:nowrap;}}
.analysis-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;}}
.analysis-block{{background:var(--white);border-radius:14px;padding:24px;border:1px solid var(--border);}}
.analysis-block h4{{font-size:1rem;font-weight:700;margin-bottom:16px;}}
.analysis-block.strengths h4{{color:var(--green);}}.analysis-block.attention h4{{color:var(--orange);}}
.analysis-list{{list-style:none;}}
.analysis-list li{{padding:10px 0;border-bottom:1px solid var(--border);font-size:0.88rem;color:#374151;display:flex;gap:10px;align-items:flex-start;line-height:1.5;}}
.analysis-list li:last-child{{border-bottom:none;}}.analysis-list li .bullet{{flex-shrink:0;}}
.rec-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:24px;}}
.rec-card{{background:var(--white);border-radius:12px;padding:18px 20px;border:1px solid var(--border);border-left:4px solid var(--a);display:flex;gap:14px;align-items:flex-start;}}
.rec-card .rec-icon{{font-size:1.5rem;flex-shrink:0;margin-top:2px;}}
.rec-card .rec-body h5{{font-size:0.88rem;font-weight:700;color:var(--p);margin-bottom:4px;}}
.rec-card .rec-body p{{font-size:0.83rem;color:#374151;line-height:1.55;}}
.rec-grid.stories .rec-card{{border-left-color:var(--p2);}}
.audience-note{{background:#f8fafc;border:1px dashed var(--border);border-radius:10px;padding:12px 18px;margin-bottom:20px;font-size:0.83rem;color:var(--muted);}}
.no-data-msg{{text-align:center;padding:40px;color:var(--muted);font-size:0.9rem;}}
.format-badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600;background:var(--al);color:var(--ad);}}
.rank-num{{font-weight:700;color:var(--p);font-size:1rem;}}
.site-footer{{background:var(--p);color:rgba(255,255,255,0.75);text-align:center;padding:28px 24px;font-size:0.85rem;margin-top:48px;}}
.site-footer strong{{color:var(--a);}}
@media(max-width:768px){{.chart-row.cols-2,.chart-row.cols-3,.analysis-grid{{grid-template-columns:1fr;}}}}
.pdf-btn{{position:fixed;top:18px;right:18px;background:linear-gradient(135deg,#003f7c,#1a5a9a);color:#fff;border:none;border-radius:10px;padding:10px 20px;font-size:0.88rem;font-weight:700;cursor:pointer;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,0.3);display:flex;align-items:center;gap:7px;transition:all .2s;}}
.pdf-btn:hover{{background:linear-gradient(135deg,#1a5a9a,#2468b0);transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,0.35);}}
@media print{{
  *{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important;}}
  .pdf-btn{{display:none!important;}}
  #rpt-actions{{display:none!important;}}
  body{{background:#fff!important;margin:0;padding:0;}}
  .site-header{{background:linear-gradient(135deg,var(--p) 0%,var(--p2) 60%,{c['header_end']} 100%)!important;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important;}}
  .site-header *{{color:#fff!important;}}
  .section-title{{color:var(--p)!important;}}
  .container{{max-width:100%!important;padding:0 12px!important;}}
  .section{{page-break-inside:avoid;}}
  .kpi-grid{{page-break-inside:avoid;}}
  .chart-box{{page-break-inside:avoid;}}
  .post-table{{page-break-inside:avoid;}}
}}
</style>"""


# ── Section builders ──────────────────────────────────────────────────────────

def _header(profile: dict, d: dict) -> str:
    tags_html = "".join(f'<span class="htag">{t}</span>' for t in profile["tags"])
    pic = d.get("picture_url", "")
    if pic:
        avatar_html = f'<img src="{pic}" alt="{profile["handle"]}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">'
    else:
        avatar_html = profile["avatar"]
    return f"""
<header class="site-header">
<div class="container">
<div class="avatar-wrap">{avatar_html}</div>
<p class="header-handle">{profile['handle']}</p>
<h1 class="header-name">{profile['name']}</h1>
<p class="header-bio">{profile['bio']}</p>
<div class="header-tags">{tags_html}</div>
<div class="header-stats">
  <div class="hstat"><div class="hstat-val">{_br(d['followers'])}</div><div class="hstat-lbl">Seguidores</div></div>
  <div class="hstat"><div class="hstat-val">{_br(d['following'])}</div><div class="hstat-lbl">Seguindo</div></div>
  <div class="hstat"><div class="hstat-val">{_br(d['media'])}</div><div class="hstat-lbl">Publicações</div></div>
</div>
<div class="period-badge">📅 Período analisado: {d['period_label']}</div>
</div>
</header>"""


def _kpis(d: dict, report_type: str) -> str:
    cards = []
    if report_type != "Só Pago":
        cards += [
            f'<div class="kpi-card"><span class="kpi-icon">📡</span><div class="kpi-val">{_br(d["total_reach"])}</div><div class="kpi-label">Alcance Total</div><span class="kpi-badge badge-blue">org + pago</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">🌱</span><div class="kpi-val">{_br(d["total_organic"])}</div><div class="kpi-label">Alcance Orgânico</div><span class="kpi-badge badge-orange">{d["organic_pct"]}% do total</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">💬</span><div class="kpi-val">{_br(d["total_interactions"])}</div><div class="kpi-label">Interações</div><span class="kpi-badge badge-blue">likes+com+saves+shares</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">📊</span><div class="kpi-val">{_br(d["org_eng_rate"], 2)}%</div><div class="kpi-label">Eng. Orgânico</div><span class="kpi-badge badge-green">benchmark 3–5%</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">❤️</span><div class="kpi-val">{_br(d["total_likes"])}</div><div class="kpi-label">Curtidas</div></div>',
            f'<div class="kpi-card"><span class="kpi-icon">💾</span><div class="kpi-val">{_br(d["total_saves"])}</div><div class="kpi-label">Salvamentos</div><span class="kpi-badge badge-gold">saves</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">🔁</span><div class="kpi-val">{_br(d["total_shares"])}</div><div class="kpi-label">Compartilhamentos</div></div>',
            f'<div class="kpi-card"><span class="kpi-icon">💬</span><div class="kpi-val">{_br(d["total_comments"])}</div><div class="kpi-label">Comentários</div></div>',
            f'<div class="kpi-card"><span class="kpi-icon">📈</span><div class="kpi-val">+{_br(d["followers_gained"])}</div><div class="kpi-label">Seguidores Ganhos</div><span class="kpi-badge badge-green">🌱 {_br(d["followers_organic_est"])} org · 💰 {_br(d["followers_paid_est"])} pago</span></div>',
        ]
    if report_type != "Só Orgânico":
        cards += [
            f'<div class="kpi-card"><span class="kpi-icon">💰</span><div class="kpi-val">R${_br(d["total_spend"], 2)}</div><div class="kpi-label">Investimento Ads</div><span class="kpi-badge badge-gold">Meta Ads</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">🎯</span><div class="kpi-val">{_br(d["total_paid_reach"])}</div><div class="kpi-label">Alcance Pago</div><span class="kpi-badge badge-blue">{d["paid_pct"]}% do total</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">👆</span><div class="kpi-val">{_br(d["total_clicks"])}</div><div class="kpi-label">Cliques (Ads)</div></div>',
            f'<div class="kpi-card"><span class="kpi-icon">👤</span><div class="kpi-val">R${_br(d["cost_per_follower"], 2)}</div><div class="kpi-label">Custo/Seguidor</div><span class="kpi-badge badge-orange">meta: &lt;R$2,00</span></div>',
        ]
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def _obs_card(d: dict, report_type: str) -> str:
    organic_note = (
        f"O alcance orgânico de <strong>{_br(d['total_organic'])} pessoas ({d['organic_pct']}%)</strong> "
        f"com engajamento orgânico de <strong>{_br(d['org_eng_rate'],2)}%</strong> "
        f"({'acima' if d['org_eng_rate'] > 5 else 'dentro'} do benchmark de 3–5%)."
    )
    paid_note = (
        f"O investimento de <strong>R${_br(d['total_spend'],2)}</strong> gerou <strong>"
        f"{_br(d['total_paid_reach'])} pessoas alcançadas ({d['paid_pct']}% do total)</strong> "
        f"com <strong>{_br(d['total_clicks'])} cliques</strong> em "
        f"{len(d['campaigns'])} campanha(s)."
    )
    if report_type == "Só Orgânico":
        body = f"Relatório focado no desempenho orgânico de {d['period_label']}. {organic_note}"
    elif report_type == "Só Pago":
        body = f"Relatório focado no tráfego pago de {d['period_label']}. {paid_note}"
    else:
        body = f"Período analisado: <strong>{d['period_label']}</strong> ({d['days']} dias). {organic_note} {paid_note}"
    return f'<div class="obs-card"><h3>📋 Sobre este Relatório</h3><p>{body}</p></div>'


def _daily_charts(d: dict, report_type: str, uid: str) -> str:
    if report_type == "Só Pago":
        return ""

    L   = _js(d["labels"])
    Ro  = _js(d["daily_organic_reach"])
    Rp  = _js(d["daily_paid_reach"])
    Li  = _js(d["daily_likes"])
    Co  = _js(d["daily_comments"])
    Sa  = _js(d["daily_saves"])
    Sh  = _js(d["daily_shares"])
    Fc  = _js(d["daily_follower_change"])

    c1 = "cDailyR_"  + uid
    c2 = "cDailyI_"  + uid
    c3 = "cDailyFc_" + uid

    js = (
        "(function(){\n"
        "var L=%s,Ro=%s,Rp=%s,Li=%s,Co=%s,Sa=%s,Sh=%s,Fc=%s;\n"
        # Chart 1 — Alcance
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:["
        "{label:'Orgânico',data:Ro,backgroundColor:'rgba(26,90,154,0.65)',stack:'s'},"
        "{label:'Pago',data:Rp,backgroundColor:'rgba(248,185,64,0.75)',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{stacked:true,ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true}}}});\n"
        # Chart 2 — Interações
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:["
        "{label:'Likes',data:Li,backgroundColor:'rgba(26,90,154,0.75)',stack:'s'},"
        "{label:'Comentários',data:Co,backgroundColor:'rgba(248,185,64,0.75)',stack:'s'},"
        "{label:'Saves',data:Sa,backgroundColor:'rgba(16,185,129,0.75)',stack:'s'},"
        "{label:'Shares',data:Sh,backgroundColor:'rgba(249,115,22,0.75)',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{stacked:true,ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true}}}});\n"
        # Chart 3 — Novos Seguidores
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:[{"
        "label:'Novos Seguidores',data:Fc,"
        "backgroundColor:Fc.map(function(v){return v>=0?'rgba(16,185,129,0.70)':'rgba(249,115,22,0.70)';})"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{display:false}},"
        "scales:{x:{ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{beginAtZero:true}}}});\n"
        "})();"
    ) % (L, Ro, Rp, Li, Co, Sa, Sh, Fc, c1, c2, c3)

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">📅 Evolução Diária — Views &amp; Alcance</h2>'
        '\n<div class="chart-row cols-1">'
        '\n<div class="chart-card"><h4>Visualizações e Alcance por Dia (Orgânico + Pago)</h4>'
        f'\n<div style="position:relative;height:300px"><canvas id="{c1}"></canvas></div></div>'
        '\n</div>'
        '\n<div class="chart-row cols-2">'
        '\n<div class="chart-card"><h4>Interações Diárias por Tipo</h4>'
        f'\n<div style="position:relative;height:260px"><canvas id="{c2}"></canvas></div></div>'
        '\n<div class="chart-card"><h4>Novos Seguidores por Dia</h4>'
        f'\n<div style="position:relative;height:260px"><canvas id="{c3}"></canvas></div>'
        '\n<p style="font-size:0.75rem;color:#9ca3af;margin-top:8px;">* Variação diária de seguidores disponível apenas nos últimos 30 dias via Instagram Insights.</p>'
        '\n</div>'
        '\n</div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _audience_section(d: dict, uid: str) -> str:
    aud = d.get("audience", {})
    if not aud.get("has_data"):
        return (
            '\n<section class="section">'
            '\n<h2 class="section-title">👥 Análise da Audiência</h2>'
            '\n<div class="no-data-msg">📭 Dados de audiência não disponíveis para esta conta no momento.<br>'
            '<small>A conta pode não ter dados demográficos suficientes ou permissão não concedida.</small></div>'
            '\n</section>'
        )

    gp   = aud["gender_pct"]
    note = (
        '<div class="audience-note">ℹ️ <strong>Observação importante:</strong> '
        'Os dados de audiência abaixo refletem o <strong>perfil atual dos seguidores da conta</strong> '
        '(dados vitalícios). Eles não são específicos do período selecionado — representam quem '
        'segue o perfil hoje.</div>'
    )

    # Gender: donut
    gen_labels = _js(["Feminino", "Masculino", "Indefinido"])
    gen_vals   = _js([gp.get("F", 0), gp.get("M", 0), gp.get("U", 0)])
    gen_colors = _js(["rgba(233,96,178,0.8)", "rgba(26,90,154,0.8)", "rgba(156,163,175,0.7)"])

    # Age: bar
    age_labels = _js(aud["age_labels"])
    age_pcts   = _js(aud["age_pcts"])

    # Countries: horizontal bar
    cty_labels = _js(aud["country_labels"])
    cty_pcts   = _js(aud["country_pcts"])

    cg = "cGender_"   + uid
    ca = "cAge_"      + uid
    cc = "cCountry_"  + uid

    js = (
        "(function(){\n"
        "var GL=%s,GV=%s,GC=%s,AL=%s,AP=%s,CL=%s,CP=%s;\n"
        # Gender donut
        "new Chart(document.getElementById('%s'),{type:'doughnut',data:{labels:GL,datasets:[{"
        "data:GV,backgroundColor:GC,borderWidth:2,borderColor:'#fff'"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'right'},"
        "tooltip:{callbacks:{label:function(ctx){return ctx.label+': '+ctx.parsed+'%%';}}}"
        "}}});\n"
        # Age bar
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:AL,datasets:[{"
        "label:'%%',data:AP,"
        "backgroundColor:'rgba(26,90,154,0.70)',borderRadius:6"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{display:false}},"
        "scales:{x:{grid:{display:false}},"
        "y:{beginAtZero:true,ticks:{callback:function(v){return v+'%%';}}}}}});\n"
        # Countries horizontal bar
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:CL,datasets:[{"
        "label:'%%',data:CP,"
        "backgroundColor:'rgba(248,185,64,0.80)',borderRadius:6"
        "}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{display:false}},"
        "scales:{x:{beginAtZero:true,ticks:{callback:function(v){return v+'%%';}},"
        "grid:{display:false}},"
        "y:{grid:{display:false}}}}});\n"
        "})();"
    ) % (gen_labels, gen_vals, gen_colors, age_labels, age_pcts, cty_labels, cty_pcts, cg, ca, cc)

    # Dominant age insight
    dom_age  = aud.get("dominant_age", "—")
    female   = gp.get("F", 0)
    male_pct = gp.get("M", 0)
    dom_gen  = "Feminino" if female >= male_pct else "Masculino"
    dom_gen_pct = max(female, male_pct)

    insight = (
        f'<div class="obs-card" style="margin-top:16px;">'
        f'<h3>🔍 Perfil da Audiência</h3>'
        f'<p>O público predominante é <strong>{dom_gen} ({dom_gen_pct}%)</strong>, '
        f'com maior concentração na faixa etária de <strong>{dom_age} anos</strong>. '
        f'O país com maior participação é <strong>{aud["country_labels"][0] if aud["country_labels"] else "—"} '
        f'({aud["country_pcts"][0] if aud["country_pcts"] else 0}%)</strong>. '
        f'Use esses dados para calibrar a linguagem, referências culturais e horário das publicações.</p>'
        f'</div>'
    )

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">👥 Análise da Audiência</h2>'
        + note
        + '\n<div class="chart-row cols-3">'
        f'\n<div class="chart-card"><h4>Distribuição por Gênero</h4>'
        f'<div style="position:relative;height:220px"><canvas id="{cg}"></canvas></div></div>'
        f'\n<div class="chart-card"><h4>Faixa Etária dos Seguidores</h4>'
        f'<div style="position:relative;height:220px"><canvas id="{ca}"></canvas></div></div>'
        f'\n<div class="chart-card"><h4>Países de Origem</h4>'
        f'<div style="position:relative;height:220px"><canvas id="{cc}"></canvas></div></div>'
        '\n</div>'
        + insight
        + '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _content_type_section(d: dict, uid: str) -> str:
    ct = d.get("content", {})
    if not ct.get("has_data"):
        return (
            '\n<section class="section">'
            '\n<h2 class="section-title">🎨 Performance por Tipo de Conteúdo</h2>'
            '\n<div class="no-data-msg">📭 Nenhuma publicação encontrada no período selecionado.</div>'
            '\n</section>'
        )

    formats = ct["formats"]
    best    = ct.get("best_format", "—")

    # Table rows
    table_rows = ""
    for f in formats:
        icon = _format_icon(f["name"])
        table_rows += (
            f"<tr><td>{icon} <strong>{f['name']}</strong></td>"
            f"<td>{f['count']}</td>"
            f"<td>{_br(f['avg_reach'])}</td>"
            f"<td>{_br(f['avg_interactions'])}</td>"
            f"<td>{_br(f['avg_eng_rate'],2)}%</td>"
            f"<td>{_br(f['avg_saves'])}</td></tr>"
        )

    # Bar chart — avg interactions per format
    fmt_names  = _js([f["name"] for f in formats])
    fmt_avgi   = _js([f["avg_interactions"] for f in formats])
    fmt_avgr   = _js([f["avg_reach"] for f in formats])
    fmt_counts = _js([f["count"] for f in formats])
    fmt_colors = _js(["rgba(26,90,154,0.75)", "rgba(248,185,64,0.80)", "rgba(16,185,129,0.75)", "rgba(249,115,22,0.75)"])

    # Donut — distribution
    c_bar   = "cFmtBar_"   + uid
    c_donut = "cFmtDonut_" + uid

    js = (
        "(function(){\n"
        "var FN=%s,FI=%s,FR=%s,FK=%s,FC=%s;\n"
        # Bar — avg interactions
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:FN,datasets:["
        "{label:'Interações Médias',data:FI,backgroundColor:FC.slice(0,FN.length),borderRadius:8},"
        "{label:'Alcance Médio',data:FR,backgroundColor:FC.slice(0,FN.length).map(function(c){return c.replace('0.75','0.25').replace('0.80','0.25');}),borderRadius:8}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{grid:{display:false}},y:{beginAtZero:true}}}});\n"
        # Donut — count distribution
        "new Chart(document.getElementById('%s'),{type:'doughnut',data:{labels:FN,datasets:[{"
        "data:FK,backgroundColor:FC.slice(0,FN.length),borderWidth:2,borderColor:'#fff'"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'right'}}}});\n"
        "})();"
    ) % (fmt_names, fmt_avgi, fmt_avgr, fmt_counts, fmt_colors, c_bar, c_donut)

    # Conclusion text
    best_icon = _format_icon(best)
    if formats:
        best_eng  = formats[0]["avg_eng_rate"]
        conclusion = (
            f"O formato <strong>{best_icon} {best}</strong> apresentou o melhor desempenho médio "
            f"com <strong>{_br(best_eng, 2)}% de engajamento</strong> por publicação. "
        )
        if len(formats) > 1:
            worst = formats[-1]
            conclusion += (
                f"Já o formato <strong>{_format_icon(worst['name'])} {worst['name']}</strong> "
                f"teve o menor engajamento médio ({_br(worst['avg_eng_rate'],2)}%) — "
                f"considere revisar a frequência ou abordagem deste formato. "
            )
        conclusion += (
            f"<strong>Recomendação:</strong> priorize {best} nas próximas semanas "
            f"e teste variações de conteúdo para manter o algoritmo favorável."
        )
    else:
        conclusion = "Dados insuficientes para conclusão automática."

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">🎨 Performance por Tipo de Conteúdo</h2>'
        '\n<div class="table-wrap"><table>'
        '\n<thead><tr><th>Formato</th><th>Qtd. Posts</th><th>Alcance Médio</th>'
        '<th>Interações Médias</th><th>Eng. Médio</th><th>Saves Médios</th></tr></thead>'
        f'\n<tbody>{table_rows}</tbody>'
        '\n</table></div>'
        '\n<div class="chart-row cols-2">'
        f'\n<div class="chart-card"><h4>Engajamento Médio por Formato</h4>'
        f'<div style="position:relative;height:260px"><canvas id="{c_bar}"></canvas></div></div>'
        f'\n<div class="chart-card"><h4>Distribuição de Posts por Formato</h4>'
        f'<div style="position:relative;height:260px"><canvas id="{c_donut}"></canvas></div></div>'
        '\n</div>'
        f'\n<div class="obs-card"><h3>💡 Conclusão</h3><p>{conclusion}</p></div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _top_posts_section(d: dict, uid: str) -> str:
    ct = d.get("content", {})
    top10 = ct.get("top_posts", [])
    if not top10:
        return ""

    # Table
    table_rows = ""
    for i, p in enumerate(top10, 1):
        icon = _format_icon(p.get("format", "Foto"))
        link = p.get("permalink", "")
        date_str = p.get("date", "")
        link_html = f'<a href="{link}" target="_blank">🔗</a>' if link else "—"
        eng_rate  = round(p["total_interactions"] / p["reach"] * 100, 2) if p.get("reach") else 0
        table_rows += (
            f"<tr>"
            f"<td><span class='rank-num'>#{i}</span></td>"
            f"<td>{date_str}</td>"
            f"<td>{icon} {p.get('format','—')}</td>"
            f"<td>{_br(p.get('reach',0))}</td>"
            f"<td>{_br(p.get('total_interactions',0))}</td>"
            f"<td>{_br(p.get('likes',0))}</td>"
            f"<td>{_br(p.get('comments',0))}</td>"
            f"<td>{_br(p.get('saves',0))}</td>"
            f"<td>{_br(eng_rate,2)}%</td>"
            f"<td>{link_html}</td>"
            f"</tr>"
        )

    # Scatter chart: reach vs interactions
    scatter_data = _js([
        {"x": p.get("reach", 0), "y": p.get("total_interactions", 0), "r": 8}
        for p in top10
    ])
    scatter_labels = _js([f"#{i+1}" for i in range(len(top10))])
    c_scatter = "cScatter_" + uid

    js = (
        "(function(){\n"
        "var SD=%s,SL=%s;\n"
        "new Chart(document.getElementById('%s'),{type:'bubble',data:{labels:SL,datasets:[{"
        "label:'Posts',data:SD,"
        "backgroundColor:'rgba(26,90,154,0.65)',"
        "borderColor:'rgba(26,90,154,1)',"
        "borderWidth:1"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{display:false},"
        "tooltip:{callbacks:{label:function(ctx){"
        "return 'Alcance: '+ctx.parsed.x+' | Interações: '+ctx.parsed.y;}}}},"
        "scales:{"
        "x:{title:{display:true,text:'Alcance'},beginAtZero:true,grid:{display:false}},"
        "y:{title:{display:true,text:'Interações'},beginAtZero:true}"
        "}}});\n"
        "})();"
    ) % (scatter_data, scatter_labels, c_scatter)

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">🏆 Ranking dos Melhores Posts</h2>'
        '\n<div class="table-wrap"><table>'
        '\n<thead><tr><th>#</th><th>Data</th><th>Formato</th><th>Alcance</th>'
        '<th>Interações</th><th>Likes</th><th>Comentários</th><th>Saves</th><th>Eng.</th><th>Link</th></tr></thead>'
        f'\n<tbody>{table_rows}</tbody>'
        '\n</table></div>'
        '\n<div class="chart-row cols-1">'
        f'\n<div class="chart-card"><h4>Comparativo de Performance: Alcance vs Engajamento</h4>'
        f'<div style="position:relative;height:300px"><canvas id="{c_scatter}"></canvas></div>'
        '<p style="font-size:0.78rem;color:#9ca3af;margin-top:8px;">Cada bolha representa um dos top posts. Quanto mais à direita = maior alcance; quanto mais acima = mais interações.</p>'
        '\n</div></div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _paid_section(d: dict, report_type: str, uid: str) -> str:
    if report_type == "Só Orgânico":
        return ""

    camps = d["campaigns"]

    # Estado vazio — sem campanhas no período
    if not camps:
        return (
            '\n<section class="section">'
            '\n<h2 class="section-title">💰 Análise de Tráfego Pago</h2>'
            '\n<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;'
            'padding:36px 24px;text-align:center;color:#6b7280;">'
            '<div style="font-size:2rem;margin-bottom:12px;">📭</div>'
            '<p style="font-weight:600;color:#374151;margin-bottom:6px;">Nenhuma campanha encontrada no período</p>'
            '<p style="font-size:0.88rem;">Não há dados de Meta Ads para o intervalo selecionado. '
            'Verifique se havia campanhas ativas nessas datas ou selecione o tipo <em>Só Orgânico</em>.</p>'
            '\n</div></section>'
        )

    rows_html = ""
    for c in camps:
        rows_html += (
            f"<tr><td>{c['name']}</td><td>{c['objective']}</td>"
            f"<td>R${_br(c['spend'],2)}</td><td>{_br(c['impressions'])}</td>"
            f"<td>{_br(c['reach'])}</td><td>{_br(c['clicks'])}</td>"
            f"<td>R${_br(c['cpm'],2)}</td><td>R${_br(c['cpc'],2)}</td>"
            f"<td>{_br(c['ctr'],2)}%</td><td>{_status_pill(c['status'])}</td></tr>"
        )
    rows_html += (
        '<tr style="background:var(--pl);font-weight:700;">'
        f'<td><strong>TOTAL</strong></td><td>—</td>'
        f'<td><strong>R${_br(d["total_spend"],2)}</strong></td>'
        f'<td><strong>{_br(d["total_impressions"])}</strong></td>'
        f'<td><strong>{_br(d["total_paid_reach"])}</strong></td>'
        f'<td><strong>{_br(d["total_clicks"])}</strong></td>'
        f'<td><strong>R${_br(d["avg_cpm"],2)}</strong></td>'
        f'<td><strong>R${_br(d["avg_cpc"],2)}</strong></td>'
        '<td>—</td><td>—</td></tr>'
    )

    c_split = "cPaidSplit_" + uid
    c_spend = "cSpend_"     + uid
    L  = _js(d["labels"])
    Ro = _js(d["daily_organic_reach"])
    Rp = _js(d["daily_paid_reach"])
    Sp = _js(d["daily_spend"])

    js = (
        "(function(){\n"
        "var L=%s,Ro=%s,Rp=%s,Sp=%s;\n"
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:["
        "{label:'Orgânico',data:Ro,backgroundColor:'rgba(26,90,154,0.65)',stack:'s'},"
        "{label:'Pago',data:Rp,backgroundColor:'rgba(248,185,64,0.75)',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{stacked:true,ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true}}}});\n"
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:[{"
        "label:'Gasto R$',data:Sp,"
        "backgroundColor:Sp.map(function(v){return v>0?'rgba(248,185,64,0.75)':'rgba(0,0,0,0)';}),"
        "borderColor:Sp.map(function(v){return v>0?'#d99a20':'transparent';}),"
        "borderWidth:1,borderRadius:4"
        "}]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{display:false}},"
        "scales:{x:{ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{beginAtZero:true,ticks:{callback:function(v){return'R$'+v.toFixed(0);}}}}}});\n"
        "})();"
    ) % (L, Ro, Rp, Sp, c_split, c_spend)

    mini_kpis = (
        f'<div class="mini-kpi"><div class="val">R${_br(d["total_spend"],2)}</div><div class="lbl">Investido</div></div>'
        f'<div class="mini-kpi"><div class="val">{_br(d["total_impressions"])}</div><div class="lbl">Impressões</div></div>'
        f'<div class="mini-kpi"><div class="val">{_br(d["total_paid_reach"])}</div><div class="lbl">Alcançadas</div></div>'
        f'<div class="mini-kpi"><div class="val">{_br(d["total_clicks"])}</div><div class="lbl">Cliques</div></div>'
        f'<div class="mini-kpi"><div class="val">R${_br(d["avg_cpm"],2)}</div><div class="lbl">CPM Médio</div></div>'
        f'<div class="mini-kpi"><div class="val">R${_br(d["cost_per_follower"],2)}</div><div class="lbl">Custo/Seguidor est.</div></div>'
    )

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">💰 Análise de Tráfego Pago</h2>'
        f'\n<div class="mini-kpi-row">{mini_kpis}</div>'
        '\n<div class="table-wrap"><table>'
        '\n<thead><tr><th>Campanha</th><th>Objetivo</th><th>Gasto</th><th>Impressões</th>'
        '<th>Alcance</th><th>Cliques</th><th>CPM</th><th>CPC</th><th>CTR</th><th>Status</th></tr></thead>'
        f'\n<tbody>{rows_html}</tbody>'
        '\n</table></div>'
        '\n<div class="chart-row cols-2">'
        '\n<div class="chart-card"><h4>Alcance Orgânico vs Pago por Dia</h4>'
        f'<div style="position:relative;height:260px"><canvas id="{c_split}"></canvas></div></div>'
        '\n<div class="chart-card"><h4>Gasto Diário em Anúncios (R$)</h4>'
        f'<div style="position:relative;height:260px"><canvas id="{c_spend}"></canvas></div></div>'
        '\n</div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _strategic(d: dict, report_type: str) -> str:
    ct       = d.get("content", {})
    aud      = d.get("audience", {})
    best_fmt = ct.get("best_format", "Reel")
    strengths  = []
    attentions = []

    if report_type != "Só Pago":
        eng = d["org_eng_rate"]
        bench_msg = "muito acima do benchmark de 3–5%" if eng > 5 else "dentro do benchmark de 3–5%"
        strengths.append(("🔥", f"Engajamento orgânico de <strong>{_br(eng,2)}%</strong> — {bench_msg} para o nicho."))

        saves = d["total_saves"]
        total_int = d["total_interactions"]
        save_pct  = round(saves / total_int * 100, 1) if total_int else 0
        if save_pct >= 8:
            strengths.append(("📌", f"<strong>{_br(saves)} salvamentos</strong> ({save_pct}% das interações) — audiência utiliza o conteúdo como referência e material de estudo."))
        else:
            attentions.append(("📎", f"Taxa de saves de <strong>{save_pct}%</strong> das interações — abaixo do ideal (8–15%). Criar mais conteúdo educativo e de referência pode aumentar os saves."))

        if d["organic_pct"] >= 40:
            strengths.append(("🌱", f"Alcance orgânico de <strong>{d['organic_pct']}%</strong> do total — boa distribuição natural do conteúdo pelo algoritmo."))
        else:
            attentions.append(("📉", f"Alcance orgânico de apenas <strong>{d['organic_pct']}%</strong> do total — alta dependência do tráfego pago para visibilidade."))

        shares = d["total_shares"]
        if shares > 100:
            strengths.append(("🔁", f"<strong>{_br(shares)} compartilhamentos</strong> no período — conteúdo com forte apelo de disseminação orgânica."))
        else:
            attentions.append(("📤", f"Apenas <strong>{_br(shares)} compartilhamentos</strong> — explorar conteúdo que instigue o share: listas, comparativos, frases de impacto."))

        comments = d["total_comments"]
        if comments > 50:
            strengths.append(("💬", f"<strong>{_br(comments)} comentários</strong> gerados — conteúdo com bom poder de conversação e conexão com o público."))

        if best_fmt:
            best_fmts = ct.get("formats", [])
            if best_fmts:
                bf = best_fmts[0]
                strengths.append(("🎯", f"Formato <strong>{_format_icon(best_fmt)} {best_fmt}</strong> com melhor desempenho: média de {_br(bf['avg_interactions'])} interações e {_br(bf['avg_eng_rate'],2)}% de engajamento por post."))

        zero_days = sum(1 for v in d["daily_organic_reach"] if v == 0)
        if zero_days > 5:
            attentions.append(("🗓️", f"<strong>{zero_days} dias sem alcance orgânico</strong> registrado — gaps de publicação ou períodos sem posts prejudicam o momentum do algoritmo."))
        elif zero_days <= 2:
            strengths.append(("📅", f"Consistência alta: apenas <strong>{zero_days} dias</strong> sem alcance registrado no período."))

        fg = d["followers_gained"]
        if fg > 0:
            strengths.append(("📈", f"<strong>+{_br(fg)} seguidores</strong> conquistados no período ({_br(d['followers_organic_est'])} orgânicos, {_br(d['followers_paid_est'])} via anúncios)."))
        else:
            attentions.append(("👤", "Nenhum crescimento de seguidores registrado no período — revisar estratégia de aquisição e chamadas para seguir o perfil."))

    if report_type != "Só Orgânico":
        for camp in d["campaigns"]:
            if camp["status"] == "best":
                strengths.append(("🏆", f"Campanha <strong>\"{camp['name']}\"</strong> com CTR {_br(camp['ctr'],2)}% e CPC R${_br(camp['cpc'],2)} — melhor desempenho do período."))
            elif camp["status"] == "warning":
                attentions.append(("⚠️", f"Campanha <strong>\"{camp['name']}\"</strong> com CPM R${_br(camp['cpm'],2)} e CTR {_br(camp['ctr'],2)}% — custo elevado, revisar criativo ou segmentação."))
        cpf = d["cost_per_follower"]
        if cpf > 0 and cpf <= 2.0:
            strengths.append(("💸", f"Custo estimado por seguidor de <strong>R${_br(cpf,2)}</strong> — dentro da meta de R$2,00."))
        elif cpf > 2.0:
            attentions.append(("💰", f"Custo estimado por seguidor de <strong>R${_br(cpf,2)}</strong> — acima da meta de R$2,00; otimizar campanhas de tráfego."))

    # Audience-based insights
    if aud.get("has_data"):
        dom_age = aud.get("dominant_age", "")
        if dom_age:
            strengths.append(("👥", f"Audiência bem definida: faixa etária dominante de <strong>{dom_age} anos</strong> — facilita a criação de conteúdo direcionado."))
        if aud["country_labels"] and aud["country_labels"][0] == "Brasil":
            pct_br = aud["country_pcts"][0] if aud["country_pcts"] else 0
            if pct_br >= 80:
                strengths.append(("🇧🇷", f"<strong>{pct_br}% da audiência é brasileira</strong> — conteúdo em português, referências nacionais e datas comemorativas do Brasil têm alto potencial."))

    # Ensure minimum 4 of each
    generic_strengths = [
        ("✅", "Presença ativa no período com publicações e interações registradas."),
        ("🌐", "Perfil com bio otimizada e identidade visual consistente contribuindo para conversão de visitantes em seguidores."),
        ("📲", "Estratégia multicanal com conteúdo orgânico + tráfego pago complementares."),
        ("🎓", "Nicho bem definido garante audiência qualificada e menor custo de aquisição em anúncios."),
    ]
    generic_attentions = [
        ("📊", "Monitorar a taxa de engajamento semanalmente para identificar quedas precoces e ajustar o calendário editorial."),
        ("🕐", "Testar horários de publicação variados para identificar o melhor momento de entrega na timeline da audiência."),
        ("🔄", "Diversificar formatos de conteúdo para não depender de apenas um tipo que pode sofrer mudança no algoritmo."),
        ("📣", "Implementar chamadas para ação (CTAs) claras em todas as publicações para estimular saves, comentários e compartilhamentos."),
    ]

    gi = 0
    while len(strengths) < 4 and gi < len(generic_strengths):
        strengths.append(generic_strengths[gi])
        gi += 1
    ai = 0
    while len(attentions) < 4 and ai < len(generic_attentions):
        attentions.append(generic_attentions[ai])
        ai += 1

    str_items = "".join(f'<li><span class="bullet">{e}</span><span>{t}</span></li>' for e, t in strengths)
    att_items = "".join(f'<li><span class="bullet">{e}</span><span>{t}</span></li>' for e, t in attentions)

    return f"""
<section class="section">
<h2 class="section-title">🧭 Análise Estratégica</h2>
<div class="analysis-grid">
<div class="analysis-block strengths">
<h4>✅ Pontos Fortes</h4>
<ul class="analysis-list">{str_items}</ul>
</div>
<div class="analysis-block attention">
<h4>⚠️ Pontos de Atenção</h4>
<ul class="analysis-list">{att_items}</ul>
</div>
</div>
</section>"""


def _recommendations(d: dict, report_type: str) -> str:
    ct       = d.get("content", {})
    aud      = d.get("audience", {})
    best_fmt = ct.get("best_format") or "Reel"
    dom_age  = aud.get("dominant_age", "25–34")
    eng      = d["org_eng_rate"]
    saves    = d["total_saves"]
    total_int = d["total_interactions"] or 1
    save_pct  = round(saves / total_int * 100, 1)

    # ── Feed recommendations (≥8) ─────────────────────────────────────────────
    feed_recs = [
        {
            "icon": "🎬",
            "title": f"Priorize {best_fmt}s no calendário editorial",
            "body": f"O formato {best_fmt} foi o que gerou maior engajamento médio no período. Mantenha pelo menos 3 {best_fmt}s por semana para aproveitar o favorecimento do algoritmo.",
        },
        {
            "icon": "📌",
            "title": "Crie mais conteúdo para salvar",
            "body": f"Sua taxa de saves está em {save_pct}% das interações. Tutoriais em carrossel, listas de referência, checklists e resumos práticos são os formatos com maior taxa de salvamento.",
        },
        {
            "icon": "🕐",
            "title": "Publique com consistência diária",
            "body": "O algoritmo do Instagram favorece contas que publicam com regularidade. Idealmente 1 post/dia no feed, com intervalo mínimo de 12h entre publicações para não competir entre si.",
        },
        {
            "icon": "💬",
            "title": "Estimule a conversa nos primeiros 30 minutos",
            "body": "O Instagram mede o engajamento nas primeiras horas após a publicação. Responda todos os comentários rapidamente e faça uma pergunta no final de cada legenda para incentivar respostas.",
        },
        {
            "icon": "🔁",
            "title": "Crie conteúdo que instigue compartilhamentos",
            "body": "Posts com dados surpreendentes, frases de impacto, comparativos ou provocações inteligentes relacionadas ao nicho tendem a ser compartilhados espontaneamente. Meta: 10+ shares por post.",
        },
        {
            "icon": "🎯",
            "title": f"Fale diretamente com quem tem {dom_age} anos",
            "body": f"Sua faixa etária dominante é {dom_age} anos. Use referências culturais, linguagem e problemas específicos desta faixa. Quanto mais específico, maior o engajamento.",
        },
        {
            "icon": "📊",
            "title": "Analise os 3 melhores posts e replique a fórmula",
            "body": "Observe o que os top posts têm em comum: tema, tom, formato, horário ou CTA. Crie variações do mesmo padrão — não reinvente sempre, refine o que já funciona.",
        },
        {
            "icon": "🔎",
            "title": "Use palavras-chave nas legendas (SEO no Instagram)",
            "body": "O Instagram usa processamento de linguagem natural para indexar posts. Inclua palavras-chave do seu nicho na primeira linha da legenda para aparecer nas buscas do app.",
        },
        {
            "icon": "📅",
            "title": "Crie séries e conteúdo temático semanal",
            "body": "Séries recorrentes (ex: 'Dica de segunda', 'Revisão de domingo') criam expectativa no público e aumentam o retorno de visitas ao perfil — fator valorizado pelo algoritmo.",
        },
        {
            "icon": "🤝",
            "title": "Colabore com outros criadores do nicho",
            "body": "Collabs e reposts entre perfis do mesmo nicho expõem sua conta para audiências qualificadas já interessadas no tema. Uma collab bem feita pode superar o alcance de 10 posts comuns.",
        },
    ]

    # ── Stories recommendations ───────────────────────────────────────────────
    stories_recs = [
        {
            "icon": "📣",
            "title": "Use stories para anunciar novos posts do feed",
            "body": "Ao publicar no feed, imediatamente compartilhe o post nos stories com um CTA: 'Vi que você pode ter perdido esse…' ou 'Esse post vai te ajudar muito, salva lá!'. Isso aumenta alcance e saves.",
        },
        {
            "icon": "🗳️",
            "title": "Enquetes para validar tema dos próximos posts",
            "body": "Use a figurinha de enquete para perguntar o que o público quer ver no feed. Além de aumentar o engajamento no story, você garante que o próximo post já tem demanda confirmada.",
        },
        {
            "icon": "🎥",
            "title": "Bastidores do conteúdo criam conexão",
            "body": "Mostre nos stories o processo de criação dos posts do feed: pesquisa, gravação, edição. Isso humaniza a conta, gera identificação e aumenta o tempo de visualização dos stories.",
        },
        {
            "icon": "⏱️",
            "title": "Reforce posts de alto alcance nos stories",
            "body": "Quando um post tiver desempenho acima da média, reposte nos stories entre 24–48h depois com um novo ângulo. 'Esse post está bombando — você já viu?' aumenta saves de quem não interagiu antes.",
        },
        {
            "icon": "📎",
            "title": "Use o sticker de link para posts com mais de 10k",
            "body": "Adicione sticker de link nos stories direcionando para os posts ou para uma página de captura. Stories com link têm swipe-up behavior que pode direcionar tráfego qualificado.",
        },
        {
            "icon": "🧠",
            "title": "Quiz nos stories reforça o conteúdo educativo do feed",
            "body": "Após publicar um post educativo no feed, crie um quiz nos stories baseado no conteúdo do post. Isso reforça o aprendizado, aumenta o retorno de quem salvou o post e mede absorção da audiência.",
        },
        {
            "icon": "🌟",
            "title": "Destaque os stories mais estratégicos",
            "body": "Crie capas padronizadas para os destaques (Dicas, Tutoriais, Resultado, Sobre) e salve stories que respondam dúvidas frequentes. O destaque funciona como um mini-site permanente do perfil.",
        },
        {
            "icon": "📆",
            "title": "Crie uma rotina semanal de stories",
            "body": "Seguidores que assistem stories diariamente têm 3x mais chance de comprar do criador. Defina um calendário: segunda = bastidores, quarta = dica rápida, sexta = enquete do próximo post.",
        },
    ]

    def _rec_card(r, cls=""):
        return (
            f'<div class="rec-card {cls}">'
            f'<div class="rec-icon">{r["icon"]}</div>'
            f'<div class="rec-body"><h5>{r["title"]}</h5><p>{r["body"]}</p></div>'
            f'</div>'
        )

    feed_html    = "".join(_rec_card(r) for r in feed_recs)
    stories_html = "".join(_rec_card(r, "stories") for r in stories_recs)

    return f"""
<section class="section">
<h2 class="section-title">💡 Recomendações Estratégicas para o Feed</h2>
<div class="rec-grid">
{feed_html}
</div>
</section>

<section class="section">
<h2 class="section-title">📖 Recomendações Estratégicas para Stories</h2>
<p style="color:#6b7280;font-size:0.9rem;margin-bottom:20px;">Como usar os stories para ampliar o alcance e o engajamento do feed:</p>
<div class="rec-grid stories">
{stories_html}
</div>
</section>"""


def _best_hours_section(d: dict) -> str:
    """Cartão com os melhores horários para publicar, baseado nos posts do período."""
    hours = d.get("best_hours", [])
    if not hours:
        return ""

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    items_html = ""
    for i, h in enumerate(hours[:5]):
        medal = medals[i] if i < len(medals) else "▪️"
        items_html += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;'
            f'background:{"var(--pl)" if i==0 else "#f9fafb"};border-radius:8px;'
            f'border:1px solid {"var(--border)" if i>0 else "var(--p2)"};margin-bottom:6px;">'
            f'<span style="font-size:1.2rem;">{medal}</span>'
            f'<span style="font-weight:{"700" if i==0 else "500"};color:var(--text);">'
            f'{h["label"]}</span>'
            f'<span style="margin-left:auto;font-size:.85rem;color:var(--muted);">'
            f'~{h["avg_interactions"]:.0f} interações/post &nbsp;·&nbsp; {h["count"]} posts</span>'
            f'</div>'
        )

    return f"""
<section class="section">
<h2 class="section-title">⏰ Melhores Horários para Publicar</h2>
<p style="font-size:.88rem;color:var(--muted);margin-bottom:16px;">
  Análise baseada nos {d.get("total_posts_fetched",0)} posts do período —
  horários com maior engajamento médio (curtidas + comentários + saves + compartilhamentos):
</p>
<div style="max-width:520px;">{items_html}</div>
<p style="font-size:.78rem;color:var(--muted);margin-top:10px;">
  ⚠️ Horários em UTC+0. Considere o fuso horário da sua audiência ao agendar.
</p>
</section>"""


def _footer(profile: dict, d: dict, generated_at: str = "") -> str:
    gen_note = f" &nbsp;|&nbsp; Gerado em {generated_at}" if generated_at else ""
    return (
        '<footer class="site-footer">'
        f'<p>{profile["footer"]} &nbsp;|&nbsp; {profile["handle"]} &nbsp;|&nbsp; '
        f'Período: {d["period_label"]} &nbsp;|&nbsp; Dados: Instagram Insights + Meta Ads Manager{gen_note}</p>'
        '<p style="font-size:0.75rem;opacity:0.65;margin-top:6px;">'
        '📋 Documento confidencial — gerado exclusivamente para uso do cliente. Não compartilhar publicamente.'
        '</p>'
        '</footer>'
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(profile: dict, data: dict, report_type: str = "Geral", generated_at: str = "") -> str:
    import time
    uid = str(int(time.time() * 1000))[-6:]
    c   = profile["colors"]

    parts = [
        "<!DOCTYPE html><html lang='pt-BR'><head>",
        "<meta charset='UTF-8'>",
        f"<title>Relatório {profile['handle']} — {data['period_label']}</title>",
        "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>",
        _css(c),
        "</head><body>",
        _header(profile, data),
        "<div class='container'>",

        # 1. Métricas do período
        "<section class='section'>",
        "<h2 class='section-title'>📈 Métricas do Período</h2>",
        _kpis(data, report_type),
        "</section>",

        # 2. Observação
        _obs_card(data, report_type),

        # 3. Evolução diária (com followers chart)
        _daily_charts(data, report_type, uid),

        # 4. Análise da audiência
        _audience_section(data, uid) if report_type != "Só Pago" else "",

        # 5. Performance por tipo de conteúdo
        _content_type_section(data, uid) if report_type != "Só Pago" else "",

        # 6. Ranking dos melhores posts
        _top_posts_section(data, uid) if report_type != "Só Pago" else "",

        # 7. Tráfego pago
        _paid_section(data, report_type, uid),

        # 8. Análise estratégica
        _strategic(data, report_type),

        # 9. Melhores horários para publicar
        _best_hours_section(data) if report_type != "Só Pago" else "",

        # 10. Recomendações feed + stories
        _recommendations(data, report_type),

        "</div>",
        _footer(profile, data, generated_at),
        "<script>Chart.defaults.font.family=\"'Segoe UI',system-ui,sans-serif\";"
        "Chart.defaults.font.size=11;Chart.defaults.color='#6b7280';"
        "window.addEventListener('message',function(e){if(e.data&&e.data.type==='dash-print')window.print();});"
        "</script>",
        "</body></html>",
    ]

    return "\n".join(parts)
