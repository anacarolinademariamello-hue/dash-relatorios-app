"""
health_score.py — Cálculo do Score de Saúde da conta (0–100).

Usado tanto pelo script semanal automático (scripts/weekly_metrics.py)
quanto pelo app manual (app.py / html_gen.py).

Critérios:
  Frequência de postagem  → 20 pts
  Engajamento orgânico    → 25 pts
  Crescimento seguidores  → 20 pts
  CTR de campanhas        → 20 pts  (neutro = 10 se sem ads)
  Consistência vs período anterior → 15 pts  (neutro = 7 sem histórico)
"""
from __future__ import annotations


def render_card_html(health: dict) -> str:
    """
    Gera o HTML do card de Score de Saúde para injetar no relatório.
    Pode ser chamado de app.py sem depender de html_gen.py.
    """
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
        d_arrow = "&#9650;" if delta >= 0 else "&#9660;"
        delta_html = (
            f'<span style="font-size:.85rem;font-weight:600;color:{d_color};margin-left:12px;">'
            f'{d_arrow} {d_sign}{delta} pts vs per&#237;odo anterior</span>'
        )

    emoji = "&#129001;" if score >= 70 else "&#128993;" if score >= 55 else "&#129000;" if score >= 35 else "&#128308;"

    label_map = [
        ("frequencia",   "Frequ&#234;ncia de postagem <span style='font-weight:400;color:#9ca3af;'>(quantos dias do per&#237;odo tiveram pelo menos 1 post)</span>",          20),
        ("engajamento",  "Engajamento org&#226;nico <span style='font-weight:400;color:#9ca3af;'>(intera&#231;&#245;es totais &#247; seguidores)</span>",                      25),
        ("crescimento",  "Crescimento de seguidores <span style='font-weight:400;color:#9ca3af;'>(seguidores ganhos &#247; total de seguidores)</span>",                      20),
        ("ctr",          "CTR de campanhas <span style='font-weight:400;color:#9ca3af;'>(taxa de clique nos an&#250;ncios — neutro 10/20 sem ads)</span>",                    20),
        ("consistencia", "Consist&#234;ncia vs per&#237;odo ant. <span style='font-weight:400;color:#9ca3af;'>(varia&#231;&#227;o do alcan&#231;e vs per&#237;odo anterior)</span>", 15),
    ]
    bars_html = ""
    for key, label, max_val in label_map:
        val       = breakdown.get(key, 0)
        pct       = int(val / max_val * 100) if max_val else 0
        bar_color = "#16a34a" if pct >= 70 else "#d97706" if pct >= 40 else "#dc2626"
        bars_html += (
            f'<div style="margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:.82rem;color:#6b7280;">{label}</span>'
            f'<span style="font-size:.82rem;font-weight:700;color:#374151;">{val}/{max_val}</span>'
            f'</div>'
            f'<div style="background:#f3f4f6;border-radius:6px;height:8px;">'
            f'<div style="background:{bar_color};width:{pct}%;height:8px;border-radius:6px;"></div>'
            f'</div></div>'
        )

    return (
        '<section class="section">'
        '<h2 class="section-title">&#127973; Score de Sa&#250;de da Conta</h2>'
        f'<div style="background:#fff;border:2px solid {color};border-radius:16px;padding:28px 32px;">'
        f'<div style="display:flex;align-items:center;gap:24px;margin-bottom:24px;flex-wrap:wrap;">'
        f'<div style="font-size:5rem;line-height:1;">{emoji}</div>'
        f'<div>'
        f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:4px;">Score de Sa&#250;de</div>'
        f'<div style="display:flex;align-items:baseline;gap:4px;">'
        f'<span style="font-size:4rem;font-weight:800;color:{color};line-height:1;">{score}</span>'
        f'<span style="font-size:1.4rem;color:#9ca3af;">/100</span>'
        f'{delta_html}'
        f'</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:{color};margin-top:4px;">{grade}</div>'
        f'</div></div>'
        f'<div style="max-width:600px;">{bars_html}</div>'
        f'<div style="margin-top:16px;padding:12px 16px;background:#f8fafc;border-radius:10px;font-size:.8rem;color:#6b7280;">'
        f'&#128161; Score calculado com base no per&#237;odo selecionado. CTR &#233; neutro (10/20) quando n&#227;o h&#225; tr&#225;fego pago.'
        f'</div></div></section>'
    )


def calculate(data: dict, prev_metrics: dict | None = None) -> dict:
    """
    Calcula o score de saúde com base nos dados processados do período.

    Args:
        data:         dict retornado por src.processor.process()
        prev_metrics: dict de métricas do período anterior (de report_history),
                      ou None se não houver histórico.

    Returns:
        {
            "score":     int,        # 0–100
            "grade":     str,        # "Excelente" | "Bom" | "Regular" | "Atenção" | "Crítico"
            "color":     str,        # cor hex para UI
            "breakdown": dict,       # pontos por critério
            "delta":     int | None, # variação vs semana anterior
        }
    """
    scores: dict[str, int] = {}

    # 1. Frequência de postagem (20 pts)
    posting_days = int(data.get("posting_days", 0) or 0)
    days         = max(int(data.get("days", 7) or 7), 1)
    post_rate    = posting_days / days
    if   post_rate >= 0.70: scores["frequencia"] = 20
    elif post_rate >= 0.50: scores["frequencia"] = 15
    elif post_rate >= 0.30: scores["frequencia"] = 10
    elif post_rate >= 0.15: scores["frequencia"] = 5
    else:                   scores["frequencia"] = 0

    # 2. Engajamento orgânico (25 pts)
    eng = float(data.get("org_eng_rate", 0) or 0)
    if   eng >= 5.0: scores["engajamento"] = 25
    elif eng >= 3.0: scores["engajamento"] = 20
    elif eng >= 1.5: scores["engajamento"] = 12
    elif eng >= 0.5: scores["engajamento"] = 6
    else:            scores["engajamento"] = 0

    # 3. Crescimento de seguidores (20 pts)
    followers        = max(int(data.get("followers", 0) or 0), 1)
    followers_gained = int(data.get("followers_gained", 0) or 0)
    growth_rate      = followers_gained / followers * 100
    if   growth_rate >= 2.0: scores["crescimento"] = 20
    elif growth_rate >= 1.0: scores["crescimento"] = 15
    elif growth_rate >= 0.3: scores["crescimento"] = 10
    elif growth_rate >= 0:   scores["crescimento"] = 5
    else:                    scores["crescimento"] = 0

    # 4. CTR de campanhas (20 pts) — neutro se sem ads
    total_spend = float(data.get("total_spend", 0) or 0)
    avg_ctr     = float(data.get("avg_ctr", 0) or 0)
    if total_spend <= 0:  scores["ctr"] = 10  # sem campanhas: neutro
    elif avg_ctr >= 2.0:  scores["ctr"] = 20
    elif avg_ctr >= 1.5:  scores["ctr"] = 16
    elif avg_ctr >= 1.0:  scores["ctr"] = 12
    elif avg_ctr >= 0.5:  scores["ctr"] = 6
    else:                 scores["ctr"] = 0

    # 5. Consistência vs período anterior (15 pts)
    if prev_metrics:
        prev_reach = float(prev_metrics.get("total_reach", 0) or 0)
        curr_reach = float(data.get("total_reach", 0) or 0)
        if prev_reach > 0:
            variation = (curr_reach - prev_reach) / prev_reach * 100
            if   variation >= 10:  scores["consistencia"] = 15
            elif variation >= -5:  scores["consistencia"] = 10
            elif variation >= -20: scores["consistencia"] = 5
            else:                  scores["consistencia"] = 0
        else:
            scores["consistencia"] = 7
    else:
        scores["consistencia"] = 7  # sem histórico: neutro

    total = sum(scores.values())

    if   total >= 85: grade, color = "Excelente", "#16a34a"
    elif total >= 70: grade, color = "Bom",       "#16a34a"
    elif total >= 55: grade, color = "Regular",   "#d97706"
    elif total >= 35: grade, color = "Atenção",   "#ea580c"
    else:             grade, color = "Crítico",   "#dc2626"

    prev_score = int(prev_metrics.get("health_score", 0) or 0) if prev_metrics else None
    delta      = (total - prev_score) if prev_score else None

    return {
        "score":     total,
        "grade":     grade,
        "color":     color,
        "breakdown": scores,
        "delta":     delta,
    }
