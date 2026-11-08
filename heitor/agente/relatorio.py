"""Relatório da auditoria: explica cada falha com a norma ou súmula.

Determinístico de propósito: o texto de cada regra é fixo e conferido, para
o relatório nunca inventar norma nem afirmar que há insalubridade.
Vocabulário segue o "seguro dizer" do CLAUDE.md (seção 11).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from heitor.agente.tipos import AchadoDict as Achado

AVISO = ("O Heitor aponta lacunas na prova documental das fichas de EPI. Ele não afirma se há "
         "insalubridade: quem a caracteriza é a perícia (art. 195 da CLT).")

SUMULA_80 = "Súmula 80 do TST: EPI aprovado (com CA) e eficaz exclui o adicional."
SUMULA_289 = ("Súmula 289 do TST: o simples fornecimento não basta; a empresa precisa garantir o uso "
              "efetivo (treinamento, troca e fiscalização).")
CRITERIO_CA = ("Critério adotado: a Nota Técnica 146/2015 do MTE exige CA válido na data da compra. "
               "Como a ficha só traz a data de entrega, CA vencido na entrega fica indeterminado até a "
               "nota fiscal mostrar a data da compra.")

_TEXTOS: dict[str, dict[str, Any]] = {
    "assinatura_ausente": {
        "titulo": "Entrega sem assinatura",
        "explicacao": "Sem a assinatura do trabalhador, a ficha não prova que o EPI foi entregue. "
                      "Entregas antigas sem assinatura não têm correção: ficam como passivo.",
        "base": [SUMULA_289],
    },
    "ca_ausente": {
        "titulo": "CA não registrado na ficha",
        "explicacao": "Sem o número do CA, a ficha não prova que o EPI era aprovado. A nota fiscal da "
                      "compra pode suprir a lacuna.",
        "base": [SUMULA_80],
    },
    "ca_nao_encontrado": {
        "titulo": "CA não encontrado na base do MTE",
        "explicacao": "O número registrado não existe na base CAEPI ou é de outro tipo de equipamento "
                      "(por exemplo, CA de óculos numa luva). Pode ser erro de digitação, de leitura ou de "
                      "registro: números parecidos são só suposição e precisam de confirmação no papel.",
        "base": [SUMULA_80],
    },
    "ca_vencido": {
        "titulo": "CA vencido na data da entrega",
        "explicacao": "O CA estava vencido quando o EPI foi entregue. Se a nota fiscal mostrar a compra "
                      "dentro da validade, a entrega é regular.",
        "base": [SUMULA_80, CRITERIO_CA],
    },
    "ca_cancelado": {
        "titulo": "CA cancelado ou suspenso",
        "explicacao": "A base do MTE marca este CA como cancelado ou suspenso, sem dizer desde quando. "
                      "Precisa de revisão manual.",
        "base": [SUMULA_80],
    },
    "ca_conflitante": {
        "titulo": "CA com dados conflitantes na base",
        "explicacao": "A base do MTE traz registros divergentes para este CA. Precisa de revisão manual.",
        "base": [SUMULA_80],
    },
    "epi_inadequado": {
        "titulo": "EPI exigido pela função não aparece na ficha",
        "explicacao": "A função exige este EPI pela tabela de riscos da empresa, mas a ficha não registra nenhuma "
                      "entrega: o trabalhador pode estar sem essa proteção. Só quando o risco é insalubre (ruído) "
                      "o período sem registro entra na exposição em R$; nos demais, o risco é de acidente.",
        "base": [SUMULA_80, SUMULA_289, "Art. 166 da CLT: a empresa deve fornecer EPI gratuitamente."],
    },
    "troca_atrasada": {
        "titulo": "EPI vencido em uso agora",
        "explicacao": "Desde a última entrega, o EPI passou da durabilidade indicada pelo fabricante: o trabalhador "
                      "pode estar sem proteção adequada hoje. A troca corrige.",
        "base": [SUMULA_289],
    },
    "troca_passado": {
        "titulo": "EPI usado além da vida útil (período já encerrado)",
        "explicacao": "Entre duas entregas, o EPI ficou em uso além da durabilidade indicada pelo fabricante. "
                      "A troca já foi feita, então não há o que corrigir agora: o período sem proteção adequada "
                      "fica como passivo e entra na exposição.",
        "base": [SUMULA_289],
    },
    "treinamento_ausente": {
        "titulo": "Sem registro de treinamento",
        "explicacao": "Sem prova do treinamento exigido, a defesa fica muito fraca. A lista de presença "
                      "pode suprir a lacuna.",
        "base": [SUMULA_289],
    },
    "entrega_sem_ficha": {
        "titulo": "Entrega da planilha sem linha na ficha de papel",
        "explicacao": "A planilha registra a entrega, mas a ficha de papel assinada não mostra essa linha. "
                      "Sem a ficha assinada, a entrega fica sem prova. Como a foto pode ter sido lida errado, "
                      "o técnico confere no papel antes de qualquer conclusão.",
        "base": [SUMULA_289],
    },
    "ficha_sem_planilha": {
        "titulo": "Linha na ficha de papel sem entrega na planilha",
        "explicacao": "A ficha de papel registra uma entrega que a planilha de controle não tem. "
                      "Ou a planilha está desatualizada, ou a linha foi lida errado da foto: conferir os dois.",
        "base": [],
    },
    "leitura_incerta": {
        "titulo": "Dado da ficha a conferir no papel",
        "explicacao": "Um dado da ficha (CA, data ou assinatura) não fecha com o resto da ficha ou com a base "
                      "do MTE. Pode ser erro de leitura da foto ou erro de registro; o técnico confere no papel.",
        "base": [],
    },
    "funcao_desconhecida": {
        "titulo": "Função fora da tabela função → EPI",
        "explicacao": "Não foi possível saber quais EPIs a função exige. Precisa de revisão manual.",
        "base": [],
    },
    "falha_de_ferramenta": {
        "titulo": "Ficha não auditada por completo",
        "explicacao": "Uma verificação falhou. A ficha precisa de revisão manual.",
        "base": [],
    },
}

_PADRAO = {"titulo": "Achado", "explicacao": "Lacuna na prova documental.", "base": []}

_TIPO_LEGIVEL = {
    "corrigivel": "Corrigível daqui para frente",
    "prova": "Prova que talvez exista",
    "passivo": "Passivo sem correção",
}


def gerar_relatorio(achados: list[Achado], exposicao: dict[str, Any] | None = None) -> dict[str, Any]:
    falhas = [a for a in achados if a.get("gravidade") in ("irregular", "risco")]
    ordem = {"irregular": 0, "risco": 1}
    falhas.sort(key=lambda a: (str(a.get("funcionario_id")), ordem[a["gravidade"]], a.get("linha") or 0))

    itens = []
    for a in falhas:
        t = _TEXTOS.get(a.get("regra", ""), _PADRAO)
        itens.append({
            "achado_id": a["id"], "funcionario_id": a.get("funcionario_id"), "linha": a.get("linha"),
            "gravidade": a["gravidade"], "tipo": _TIPO_LEGIVEL.get(a.get("tipo", ""), a.get("tipo")),
            "titulo": t["titulo"], "evidencia": a.get("evidencia", ""), "explicacao": t["explicacao"],
            "base_legal": t["base"], "acao": a.get("acao_sugerida", ""),
        })

    relatorio: dict[str, Any] = {
        "aviso": AVISO,
        "resumo": {
            "funcionarios": len({a.get("funcionario_id") for a in falhas}),
            "por_gravidade": dict(Counter(a["gravidade"] for a in falhas)),
            "por_tipo": dict(Counter(_TIPO_LEGIVEL.get(a.get("tipo", ""), a.get("tipo")) for a in falhas)),
        },
        "itens": itens,
    }
    if exposicao:
        relatorio["exposicao"] = {
            "total_brl": exposicao.get("total_brl"),
            "salario_minimo": exposicao.get("salario_minimo"),
            "descricao": "Exposição potencial máxima, se a perícia confirmar a insalubridade.",
        }
    relatorio["texto"] = _texto(relatorio)
    return relatorio


def _texto(r: dict[str, Any]) -> str:
    """Versão em texto corrido, para a interface ou um e-mail."""
    linhas = [r["aviso"], ""]
    atual = None
    for it in r["itens"]:
        if it["funcionario_id"] != atual:
            atual = it["funcionario_id"]
            linhas.append(f"Funcionário {atual}")
        onde = f"linha {it['linha']}" if it["linha"] else "ficha inteira"
        linhas.append(f"  [{it['gravidade'].upper()}] {it['titulo']} ({onde}): {it['evidencia']}.")
        linhas.append(f"    {it['explicacao']}")
        for b in it["base_legal"]:
            linhas.append(f"    • {b}")
        if it["acao"]:
            linhas.append(f"    Ação: {it['acao']}.")
    if "exposicao" in r and r["exposicao"].get("total_brl") is not None:
        e = r["exposicao"]
        sm = f" (salário mínimo usado: {reais(e['salario_minimo'])})" if e.get("salario_minimo") else ""
        linhas += ["", f"{e['descricao']} Total: {reais(e['total_brl'])}{sm}."]
    return "\n".join(linhas)


def reais(valor: float) -> str:
    """1518.0 -> 'R$ 1.518,00'."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
