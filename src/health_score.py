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
