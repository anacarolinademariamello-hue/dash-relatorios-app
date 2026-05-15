"""
Generates the full HTML analytics report from processed data + profile config.
report_type: "Geral" | "Só Orgânico" | "Só Pago"
"""
import json


# ── Helpers ──────────────────────────────────────────────────────────────────

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


# ── CSS ──────────────────────────────────────────────────────────────────────

def _css(c: dict) -> str:
    return f"""<style>
:root{{--p:{c['p']};--p2:{c['p2']};--a:{c['a']};--ad:{c['ad']};--al:{c['al']};--pl:{c['pl']};--bg:{c['bg']};--white:#fff;--text:#1a1a2e;--muted:#6b7280;--border:#dde3ed;--green:#10b981;--orange:#f97316;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;font-size:15px;}}
a{{color:var(--p2);text-decoration:none;}}a:hover{{text-decoration:underline;}}
.site-header{{background:linear-gradient(135deg,var(--p) 0%,var(--p2) 60%,{c['header_end']} 100%);color:#fff;padding:48px 24px 40px;text-align:center;position:relative;overflow:hidden;}}
.site-header::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 80% 20%,rgba(255,255,255,0.10) 0%,transparent 60%);pointer-events:none;}}
.avatar-wrap{{width:90px;height:90px;border-radius:50%;background:linear-gradient(135deg,var(--a),var(--ad));display:flex;align-items:center;justify-content:center;font-size:2.4rem;margin:0 auto 16px;box-shadow:0 4px 20px rgba(0,0,0,0.3);border:3px solid rgba(255,255,255,0.3);}}
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
.section{{padding:48px 0 16px;}}
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
.site-footer{{background:var(--p);color:rgba(255,255,255,0.75);text-align:center;padding:28px 24px;font-size:0.85rem;margin-top:48px;}}
.site-footer strong{{color:var(--a);}}
@media(max-width:768px){{.chart-row.cols-2,.chart-row.cols-3,.analysis-grid{{grid-template-columns:1fr;}}}}
</style>"""


# ── Section builders ──────────────────────────────────────────────────────────

def _header(profile: dict, d: dict) -> str:
    tags_html = "".join(f'<span class="htag">{t}</span>' for t in profile["tags"])
    return f"""
<header class="site-header">
<div class="container">
<div class="avatar-wrap">{profile['avatar']}</div>
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
            f'<div class="kpi-card"><span class="kpi-icon">📊</span><div class="kpi-val">{_br(d["org_eng_rate"], 2)}%</div><div class="kpi-label">Eng. Orgânico</div><span class="kpi-badge badge-green">🔥 vs benchmark 3-5%</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">❤️</span><div class="kpi-val">{_br(d["total_likes"])}</div><div class="kpi-label">Curtidas</div><span class="kpi-badge badge-blue">likes</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">🔖</span><div class="kpi-val">{_br(d["total_saves"])}</div><div class="kpi-label">Salvamentos</div><span class="kpi-badge badge-gold">saves</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">📈</span><div class="kpi-val">+{_br(d["followers_gained"])}</div><div class="kpi-label">Seguidores Ganhos</div><span class="kpi-badge badge-green">🌱 {_br(d["followers_organic_est"])} org · 💰 {_br(d["followers_paid_est"])} pago</span></div>',
        ]
    if report_type != "Só Orgânico":
        cards += [
            f'<div class="kpi-card"><span class="kpi-icon">💰</span><div class="kpi-val">R${_br(d["total_spend"], 2)}</div><div class="kpi-label">Investimento Ads</div><span class="kpi-badge badge-gold">Meta Ads</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">🎯</span><div class="kpi-val">{_br(d["total_paid_reach"])}</div><div class="kpi-label">Alcance Pago</div><span class="kpi-badge badge-blue">{d["paid_pct"]}% do total</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">👆</span><div class="kpi-val">{_br(d["total_clicks"])}</div><div class="kpi-label">Cliques (Ads)</div><span class="kpi-badge badge-blue">total campanhas</span></div>',
            f'<div class="kpi-card"><span class="kpi-icon">👤</span><div class="kpi-val">R${_br(d["cost_per_follower"], 2)}</div><div class="kpi-label">Custo/Seguidor est.</div><span class="kpi-badge badge-orange">meta: &lt;R$2,00</span></div>',
        ]
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def _obs_card(d: dict, report_type: str) -> str:
    organic_note = (
        f"O alcance orgânico de <strong>{_br(d['total_organic'])} pessoas ({d['organic_pct']}%)</strong> "
        f"com engajamento orgânico de <strong>{_br(d['org_eng_rate'],2)}%</strong> — "
        f"muito acima do benchmark de 3–5%."
    )
    paid_note = (
        f"O investimento de <strong>R${_br(d['total_spend'],2)}</strong> gerou <strong>"
        f"{_br(d['total_paid_reach'])} pessoas alcançadas ({d['paid_pct']}% do total)</strong> "
        f"com <strong>{_br(d['total_clicks'])} cliques</strong> distribuídos em "
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

    L  = _js(d["labels"])
    Ro = _js(d["daily_organic_reach"])
    Rp = _js(d["daily_paid_reach"])
    Li = _js(d["daily_likes"])
    Co = _js(d["daily_comments"])
    Sa = _js(d["daily_saves"])
    Sh = _js(d["daily_shares"])

    chart1_id = "cDailyR_" + uid
    chart2_id = "cDailyI_" + uid

    # Build JS with % formatting so { } chars don't need escaping
    js = (
        "(function(){\n"
        "var L=%s,Ro=%s,Rp=%s,Li=%s,Co=%s,Sa=%s,Sh=%s;\n"
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:["
        "{label:'Orgânico',data:Ro,backgroundColor:'rgba(26,90,154,0.65)',stack:'s'},"
        "{label:'Pago',data:Rp,backgroundColor:'rgba(248,185,64,0.75)',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{stacked:true,ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true}}}});\n"
        "new Chart(document.getElementById('%s'),{type:'bar',data:{labels:L,datasets:["
        "{label:'Likes',data:Li,backgroundColor:'rgba(26,90,154,0.75)',stack:'s'},"
        "{label:'Comentários',data:Co,backgroundColor:'rgba(248,185,64,0.75)',stack:'s'},"
        "{label:'Saves',data:Sa,backgroundColor:'rgba(16,185,129,0.75)',stack:'s'},"
        "{label:'Shares',data:Sh,backgroundColor:'rgba(249,115,22,0.75)',stack:'s'}"
        "]},options:{responsive:true,maintainAspectRatio:false,"
        "plugins:{legend:{position:'top'}},"
        "scales:{x:{stacked:true,ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true}}}});\n"
        "})();"
    ) % (L, Ro, Rp, Li, Co, Sa, Sh, chart1_id, chart2_id)

    return (
        '\n<section class="section">'
        '\n<h2 class="section-title">📅 Evolução Diária</h2>'
        '\n<div class="chart-row cols-1">'
        '\n<div class="chart-card"><h4>Alcance Orgânico vs Pago por Dia</h4>'
        f'\n<div style="position:relative;height:320px"><canvas id="{chart1_id}"></canvas></div></div>'
        '\n</div>'
        '\n<div class="chart-row cols-1">'
        '\n<div class="chart-card"><h4>Interações Diárias (Likes · Comentários · Saves · Shares)</h4>'
        f'\n<div style="position:relative;height:260px"><canvas id="{chart2_id}"></canvas></div></div>'
        '\n</div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _paid_section(d: dict, report_type: str, uid: str) -> str:
    if report_type == "Só Orgânico":
        return ""

    camps = d["campaigns"]

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

    chart_split_id = "cPaidSplit_" + uid
    chart_spend_id = "cSpend_" + uid

    L  = _js(d["labels"])
    Ro = _js(d["daily_organic_reach"])
    Rp = _js(d["daily_paid_reach"])
    Sp = _js(d["daily_spend"])

    # Build JS with % formatting so { } chars don't need escaping
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
    ) % (L, Ro, Rp, Sp, chart_split_id, chart_spend_id)

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
        f'\n<div style="position:relative;height:260px"><canvas id="{chart_split_id}"></canvas></div></div>'
        '\n<div class="chart-card"><h4>Gasto Diário em Anúncios (R$)</h4>'
        f'\n<div style="position:relative;height:260px"><canvas id="{chart_spend_id}"></canvas></div></div>'
        '\n</div>'
        '\n</section>'
        '\n<script>\n' + js + '\n</script>'
    )


def _strategic(d: dict, report_type: str) -> str:
    strengths = []
    attentions = []

    if report_type != "Só Pago":
        eng = d["org_eng_rate"]
        bench_msg = "muito acima do benchmark de 3–5%" if eng > 5 else "dentro do benchmark de 3–5%"
        strengths.append(("🔥", f"Engajamento orgânico de <strong>{_br(eng,2)}%</strong> — {bench_msg} para o nicho."))

        saves = d["total_saves"]
        total_int = d["total_interactions"]
        save_pct = round(saves / total_int * 100, 1) if total_int else 0
        if save_pct >= 10:
            strengths.append(("📌", f"<strong>{_br(saves)} salvamentos</strong> ({save_pct}% das interações) — audiência usa o conteúdo como referência e material de estudo."))

        if d["organic_pct"] >= 40:
            strengths.append(("🌱", f"Alcance orgânico de <strong>{d['organic_pct']}%</strong> do total — boa distribuição natural do conteúdo pelo algoritmo."))
        else:
            attentions.append(("📉", f"Alcance orgânico de apenas <strong>{d['organic_pct']}%</strong> do total — dependência elevada do tráfego pago para visibilidade."))

        shares = d["total_shares"]
        if shares > 200:
            strengths.append(("🔁", f"<strong>{_br(shares)} compartilhamentos</strong> no período — conteúdo com forte apelo de disseminação orgânica."))

    if report_type != "Só Orgânico":
        for camp in d["campaigns"]:
            if camp["status"] == "best":
                strengths.append(("🏆", f"Campanha <strong>\"{camp['name']}\"</strong> com CTR {_br(camp['ctr'],2)}% e CPC R${_br(camp['cpc'],2)} — melhor desempenho do período."))
            elif camp["status"] == "warning":
                attentions.append(("⚠️", f"Campanha <strong>\"{camp['name']}\"</strong> com CPM R${_br(camp['cpm'],2)} — custo elevado, revisar criativo ou segmentação."))

        cpf = d["cost_per_follower"]
        if cpf <= 2.0:
            strengths.append(("💸", f"Custo estimado por seguidor de <strong>R${_br(cpf,2)}</strong> — dentro da meta de R$2,00."))
        else:
            attentions.append(("💰", f"Custo estimado por seguidor de <strong>R${_br(cpf,2)}</strong> — acima da meta de R$2,00; otimizar campanhas de tráfego."))

    if report_type != "Só Pago":
        zero_days = sum(1 for v in d["daily_organic_reach"] if v == 0)
        if zero_days > 3:
            attentions.append(("🗓️", f"<strong>{zero_days} dias sem alcance orgânico</strong> no período — gaps de publicação prejudicam o momentum do algoritmo."))

    if not strengths:
        strengths.append(("✅", "Dados insuficientes para análise de pontos fortes no período selecionado."))
    if not attentions:
        attentions.append(("💡", "Nenhum ponto crítico identificado neste período — manter a estratégia atual."))

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


def _footer(profile: dict, d: dict) -> str:
    return (
        '<footer class="site-footer">'
        f'<p>{profile["footer"]} &nbsp;|&nbsp; {profile["handle"]} &nbsp;|&nbsp; '
        f'Período: {d["period_label"]} &nbsp;|&nbsp; Dados: Instagram Insights + Meta Ads Manager</p>'
        '</footer>'
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(profile: dict, data: dict, report_type: str = "Geral") -> str:
    import time
    uid = str(int(time.time() * 1000))[-6:]
    c = profile["colors"]

    parts = [
        "<!DOCTYPE html><html lang='pt-BR'><head>",
        "<meta charset='UTF-8'>",
        f"<title>Relatório {profile['handle']} — {data['period_label']}</title>",
        "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>",
        _css(c),
        "</head><body>",
        _header(profile, data),
        "<div class='container'>",
        "<section class='section'>",
        "<h2 class='section-title'>📈 Métricas do Período</h2>",
        _kpis(data, report_type),
        "</section>",
        _obs_card(data, report_type),
    ]

    if report_type != "Só Pago":
        parts.append(_daily_charts(data, report_type, uid))

    if report_type != "Só Orgânico":
        parts.append(_paid_section(data, report_type, uid))

    parts += [
        _strategic(data, report_type),
        "</div>",
        _footer(profile, data),
        "<script>Chart.defaults.font.family=\"'Segoe UI',system-ui,sans-serif\";Chart.defaults.font.size=11;Chart.defaults.color='#6b7280';</script>",
        "</body></html>",
    ]

    return "\n".join(parts)
