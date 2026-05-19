"""
ai_strategic.py — Análise estratégica gerada pelo Claude com base nos dados reais do relatório.

Substitui os templates estáticos _NICHE_STRATEGIC por insights personalizados
que consideram métricas reais, metas do cliente, audiência, nicho e performance de campanhas.

Retorna: {"strengths": [(emoji, html_text), ...], "attentions": [(emoji, html_text), ...]}
Fallback: None (html_gen.py usa a lógica atual nesse caso)
"""
import json
import re


def _build_prompt(data: dict, profile: dict, report_type: str) -> str:
    name         = profile.get("name", "o cliente")
    nicho        = profile.get("nicho", "")
    sub_nicho    = profile.get("sub_nicho", "")
    publico_alvo = profile.get("publico_alvo", "")
    goals        = profile.get("goals") or {}
    period       = data.get("period_label", "")

    def _br(v, d=0):
        try:
            s = f"{float(v):,.{d}f}" if d else f"{int(round(float(v))):,}"
            return s.replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return str(v)

    # ── Métricas orgânicas ────────────────────────────────────────────────────
    org_lines = []
    if report_type != "Só Pago":
        org_lines += [
            f"- Alcance total: {_br(data.get('total_reach', 0))} "
            f"({data.get('organic_pct', 0):.0f}% orgânico, {data.get('paid_pct', 0):.0f}% pago)",
            f"- Engajamento orgânico: {_br(data.get('org_eng_rate', 0), 2)}%",
            f"- Interações totais: {_br(data.get('total_interactions', 0))} "
            f"(likes {_br(data.get('total_likes',0))}, comentários {_br(data.get('total_comments',0))}, "
            f"saves {_br(data.get('total_saves',0))}, shares {_br(data.get('total_shares',0))})",
            f"- Seguidores ganhos: +{_br(data.get('followers_gained', 0))} "
            f"({_br(data.get('followers_organic_est',0))} orgânicos, "
            f"{_br(data.get('followers_paid_est',0))} via anúncios)",
        ]
        ct = data.get("content", {})
        if ct.get("best_format"):
            org_lines.append(f"- Formato com melhor desempenho: {ct['best_format']}")
        fmts = ct.get("formats", [])
        if fmts:
            fmt_str = " | ".join(
                f"{f['type']}: {f['count']} posts, eng {f['avg_eng_rate']:.1f}%, "
                f"alcance médio {int(f['avg_reach'])}"
                for f in fmts[:4]
            )
            org_lines.append(f"- Performance por formato: {fmt_str}")
        zero_days = sum(1 for v in data.get("daily_organic_reach", []) if v == 0)
        org_lines.append(f"- Dias sem alcance registrado: {zero_days}")

    # ── Métricas pagas ────────────────────────────────────────────────────────
    paid_lines = []
    if report_type != "Só Orgânico":
        paid_lines += [
            f"- Gasto em anúncios: R${_br(data.get('total_spend',0), 2)}",
            f"- CTR médio: {_br(data.get('avg_ctr',0), 2)}%",
            f"- CPM médio: R${_br(data.get('avg_cpm',0), 2)}",
            f"- CPC médio: R${_br(data.get('avg_cpc',0), 2)}",
        ]
        cpf = data.get("cost_per_follower", 0)
        if cpf:
            paid_lines.append(f"- Custo estimado por seguidor: R${_br(cpf, 2)}")
        for c in data.get("campaigns", [])[:5]:
            status_label = {"best": "melhor desempenho", "warning": "atenção", "ok": "regular", "ended": "encerrada"}.get(c.get("status",""), "")
            paid_lines.append(
                f"- Campanha '{c['name']}' ({c.get('objective','')}) — "
                f"CTR {c.get('ctr',0):.2f}% | CPM R${c.get('cpm',0):.2f} | "
                f"CPC R${c.get('cpc',0):.2f} | status: {status_label}"
            )

    # ── Audiência ─────────────────────────────────────────────────────────────
    aud = data.get("audience", {})
    aud_lines = []
    if aud.get("has_data"):
        gender = aud.get("gender_pct", {})
        aud_lines.append(
            f"- Gênero: {gender.get('F',0):.0f}% feminino / {gender.get('M',0):.0f}% masculino"
        )
        if aud.get("dominant_age"):
            aud_lines.append(f"- Faixa etária dominante: {aud['dominant_age']} anos")
        if aud.get("country_labels"):
            top_country = aud["country_labels"][0]
            top_pct     = aud["country_pcts"][0] if aud.get("country_pcts") else 0
            aud_lines.append(f"- País dominante: {top_country} ({top_pct:.0f}%)")

    # ── Metas vs real ─────────────────────────────────────────────────────────
    goals_lines = []
    if goals and report_type != "Só Orgânico":
        def _gn(k):
            try:
                return float(goals.get(k) or 0)
            except Exception:
                return 0.0
        pairs = [
            ("ctr_minimo",  "CTR mínimo (%)",           data.get("avg_ctr", 0),  True),
            ("cpm_maximo",  "CPM máximo (R$)",           data.get("avg_cpm", 0),  False),
            ("cpc_maximo",  "CPC máximo (R$)",           data.get("avg_cpc", 0),  False),
            ("custo_por_seguidor", "Custo/seguidor (R$)", data.get("cost_per_follower",0), False),
        ]
        for key, label, real, higher_is_better in pairs:
            g = _gn(key)
            r = float(real)
            if g > 0 and r > 0:
                met = (r >= g) if higher_is_better else (r <= g)
                status = "✅ dentro da meta" if met else "❌ fora da meta"
                goals_lines.append(f"- {label}: meta {g:.2f} | real {r:.2f} → {status}")

    # ── Best hours ────────────────────────────────────────────────────────────
    best_hours = data.get("best_hours", [])
    hours_str = ""
    if best_hours:
        hours_str = "Melhores horários: " + ", ".join(
            f"{h['label']} ({h['avg_interactions']:.0f} interações médias)"
            for h in best_hours[:3]
        )

    # ── Monta o prompt ────────────────────────────────────────────────────────
    org_section  = "\n".join(org_lines)  if org_lines  else "(relatório só pago)"
    paid_section = "\n".join(paid_lines) if paid_lines else "(relatório só orgânico)"
    aud_section  = "\n".join(aud_lines)  if aud_lines  else "Sem dados de audiência disponíveis."
    goals_section = "\n".join(goals_lines) if goals_lines else "Sem metas configuradas para este cliente."

    return f"""Você é um estrategista sênior de marketing digital especializado em Instagram e Meta Ads no mercado brasileiro. Analise os dados abaixo de um relatório real e gere uma análise estratégica honesta, específica e acionável.

## CLIENTE
- Nome: {name}
- Nicho: {nicho or "Não informado"}{f" › {sub_nicho}" if sub_nicho else ""}
- Público-alvo: {publico_alvo or "Não informado"}
- Período: {period}
- Tipo de relatório: {report_type}

## MÉTRICAS ORGÂNICAS
{org_section}

## MÉTRICAS PAGAS
{paid_section}

## AUDIÊNCIA
{aud_section}

## METAS VS REAL
{goals_section}

## MELHORES HORÁRIOS
{hours_str or "Sem dados suficientes."}

## SUA TAREFA

Gere uma análise estratégica com EXATAMENTE este formato JSON. Não adicione nada fora do JSON.

Regras:
- Mínimo 4 e máximo 6 itens em cada lista
- Cada item DEVE ser baseado nos dados reais acima — nada genérico
- Use <strong> para destacar números e termos-chave no texto
- Texto em português brasileiro, tom profissional mas direto
- "attentions" deve incluir recomendações concretas, não só observações
- Se os dados mostrarem algo muito bom, coloque em strengths; se tiver problema claro, em attentions
- Considere o nicho do cliente para contextualizar os insights
- Emoji deve ser relevante ao conteúdo do item

```json
{{
  "strengths": [
    {{"emoji": "🔥", "text": "Texto com <strong>números reais</strong> e contexto específico do cliente."}},
    {{"emoji": "📌", "text": "..."}}
  ],
  "attentions": [
    {{"emoji": "⚠️", "text": "Texto com recomendação concreta baseada nos dados."}},
    {{"emoji": "📊", "text": "..."}}
  ]
}}
```"""


def generate_strategic_analysis(data: dict, profile: dict, report_type: str) -> dict | None:
    """
    Chama Claude para gerar análise estratégica personalizada.
    Retorna dict com "strengths" e "attentions" como listas de (emoji, html_text).
    Retorna None em caso de erro — html_gen.py usa fallback estático.
    """
    try:
        import streamlit as st
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or st.secrets.get("anthropic_api_key")
    except Exception:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return None

    try:
        import anthropic
        client  = anthropic.Anthropic(api_key=api_key)
        prompt  = _build_prompt(data, profile, report_type)
        message = client.messages.create(
            model="claude-haiku-4-5",      # rápido e barato para análise de relatório
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Extrai JSON mesmo se vier com texto extra
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return None
        parsed = json.loads(json_match.group(0))

        def _to_tuples(items):
            result = []
            for item in items:
                if isinstance(item, dict):
                    result.append((item.get("emoji", "•"), item.get("text", "")))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    result.append(tuple(item))
            return result

        strengths  = _to_tuples(parsed.get("strengths", []))
        attentions = _to_tuples(parsed.get("attentions", []))

        if len(strengths) >= 2 and len(attentions) >= 2:
            return {"strengths": strengths, "attentions": attentions}

        return None

    except Exception:
        return None
