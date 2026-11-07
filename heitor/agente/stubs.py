"""Stubs das funções do Gustavo (dados/) e do Pierre (api/).

Mesmas assinaturas do CLAUDE.md, para o agente rodar de ponta a ponta antes
das funções reais ficarem prontas. ferramentas.py troca cada stub pela função
real assim que ela existir (veja _importar ali).

O formato de retorno de consulta_ca, exigencia_funcao, buscar_ca_proximo e
calcula_exposicao NÃO está no contrato: é a proposta da Sofia, a combinar.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta
from typing import Any

from heitor.agente.assinatura import EXPLICACAO as EXPLICACAO_ASSINATURA
from heitor.agente.tipos import AchadoDict as Achado, LinhaDict as Linha, PendenciaDict as Pendencia

# ---------------------------------------------------------------- Gustavo ---

# CAs reais verificados (CLAUDE.md, seção 5). Validades aproximadas para o stub.
_CAS: dict[str, dict[str, Any]] = {
    "29637": {"equipamento": "capacete", "validade": "2030-12-31", "situacao": "VÁLIDO"},
    "9182": {"equipamento": "calçado", "validade": "2029-06-30", "situacao": "VÁLIDO"},
    "12844": {"equipamento": "calçado", "validade": "2029-06-30", "situacao": "VÁLIDO"},
    "10344": {"equipamento": "óculos", "validade": "2028-12-31", "situacao": "VÁLIDO"},
    "21245": {"equipamento": "luva", "validade": "2029-01-31", "situacao": "VÁLIDO",
              "lacunas": [("2024-04-29", "2024-06-24")]},
    "17664": {"equipamento": "protetor auditivo", "validade": "2030-03-31", "situacao": "VÁLIDO"},
    "28499": {"equipamento": "calçado", "validade": "2020-10-02", "situacao": "VENCIDO"},
}

_FUNCOES: dict[str, dict[str, Any]] = {
    "pedreiro": {"agente_nocivo": "ruído", "grau": 0.20,
                 "epis": [{"epi": "protetor auditivo", "vida_util_dias": 90},
                          {"epi": "capacete", "vida_util_dias": 730},
                          {"epi": "calçado", "vida_util_dias": 180}]},
    "servente": {"agente_nocivo": "ruído", "grau": 0.20,
                 "epis": [{"epi": "protetor auditivo", "vida_util_dias": 90},
                          {"epi": "capacete", "vida_util_dias": 730},
                          {"epi": "calçado", "vida_util_dias": 180}]},
    "carpinteiro": {"agente_nocivo": "ruído", "grau": 0.20,
                    "epis": [{"epi": "protetor auditivo", "vida_util_dias": 90},
                             {"epi": "óculos", "vida_util_dias": 365}]},
    "armador": {"agente_nocivo": "ruído", "grau": 0.20,
                "epis": [{"epi": "protetor auditivo", "vida_util_dias": 90},
                         {"epi": "luva", "vida_util_dias": 30}]},
}

_SINONIMOS = {
    "protetor auricular": "protetor auditivo", "plug": "protetor auditivo", "abafador": "protetor auditivo",
    "bota": "calçado", "botina": "calçado", "sapato": "calçado",
    "luva de raspa": "luva", "luvas": "luva", "oculos": "óculos", "óculos de proteção": "óculos",
}


def categoria_epi(nome: str | None) -> str | None:
    if not nome:
        return None
    n = nome.strip().lower()
    for chave, cat in _SINONIMOS.items():
        if chave in n:
            return cat
    for cat in {e["epi"] for f in _FUNCOES.values() for e in f["epis"]}:
        if cat in n:
            return cat
    return n


def consulta_ca(numero: str, data: str) -> dict[str, Any]:
    ca = _CAS.get(str(numero).strip())
    if not ca:
        return {"numero": numero, "encontrado": False}
    valido = data <= ca["validade"] and not any(a <= data <= b for a, b in ca.get("lacunas", []))
    return {"numero": numero, "encontrado": True, "valido_na_data": valido,
            "validade": ca["validade"], "situacao": ca["situacao"], "equipamento": ca["equipamento"],
            "conflito": False}


def buscar_ca_proximo(numero: str) -> list[dict[str, Any]]:
    numero = str(numero).strip()
    parecidos = [n for n in _CAS if len(n) == len(numero) and sum(a != b for a, b in zip(n, numero)) == 1]
    return [{"numero": n, "equipamento": _CAS[n]["equipamento"], "confianca": "baixa"} for n in parecidos]


def exigencia_funcao(funcao: str) -> dict[str, Any]:
    f = _FUNCOES.get((funcao or "").strip().lower())
    if not f:
        return {"funcao": funcao, "encontrada": False}
    return {"funcao": funcao, "encontrada": True, **f}


_ids_achado = itertools.count(1)


def _achado(linha: Linha | None, funcionario_id: str, regra: str, gravidade: str, tipo: str,
            evidencia: str, acao: str) -> Achado:
    return {"id": f"a-{next(_ids_achado)}", "funcionario_id": funcionario_id,
            "linha": linha.get("linha") if linha else None, "regra": regra, "gravidade": gravidade,
            "tipo": tipo, "evidencia": evidencia, "acao_sugerida": acao}


def audita_linha(linha: Linha, funcao: str) -> list[Achado]:
    fid, n = linha.get("funcionario_id", "?"), linha.get("linha")
    achados: list[Achado] = []
    conf_ass = (linha.get("confianca") or {}).get("assinatura", 1.0)
    tipo_ass = linha.get("assinatura_tipo")
    if tipo_ass in EXPLICACAO_ASSINATURA:
        texto = EXPLICACAO_ASSINATURA[tipo_ass].format(t=linha.get("assinatura_texto"))
        # Decisão do time: entrega sem linha na ficha (e linha fora da planilha) é risco, nunca irregular.
        gravidade = "irregular" if conf_ass >= 0.7 and tipo_ass != "sem_linha_na_ficha" else "risco"
        achados.append(_achado(linha, fid, "assinatura_ausente", gravidade, "passivo" if gravidade == "irregular" else "prova",
                               f"linha {n}, {texto}", "conferir a assinatura na ficha física"))
    elif linha.get("assinatura") is None or (linha.get("assinatura") is False and conf_ass < 0.7):
        # PROPOSTA ao Gustavo: leitura incerta da assinatura é risco, nunca irregular.
        achados.append(_achado(linha, fid, "assinatura_ausente", "risco", "prova",
                               f"linha {n}, assinatura incerta na leitura (confiança {conf_ass:.2f})",
                               "conferir a assinatura na ficha física"))
    elif linha.get("assinatura") is False:
        achados.append(_achado(linha, fid, "assinatura_ausente", "irregular", "passivo",
                               f"linha {n}, sem assinatura", "colher assinatura nas próximas entregas"))
    ca, data = linha.get("ca"), linha.get("data")
    conf_ca = linha.get("conferencia_ca")
    if ca and conf_ca and conf_ca.get("confere") is False:
        # PROPOSTA ao Gustavo/Pierre: regra "ca_nao_confere" no contrato. Leitura duvidosa nunca vira "CA vencido".
        achados.append(_achado(linha, fid, "ca_nao_encontrado", "risco", "prova",
                               f"linha {n}, {conf_ca['motivo']}", "conferir o CA na ficha física"))
        return achados
    if not ca:
        achados.append(_achado(linha, fid, "ca_ausente", "risco", "prova",
                               f"linha {n}, campo CA vazio", "pedir nota fiscal ao RH"))
    elif data:
        r = consulta_ca(ca, data)
        if not r["encontrado"]:
            achados.append(_achado(linha, fid, "ca_nao_encontrado", "risco", "prova",
                                   f"linha {n}, CA {ca} não está na base", "confirmar o CA com o RH"))
        elif not r["valido_na_data"]:
            achados.append(_achado(linha, fid, "ca_vencido", "risco", "prova",
                                   f"linha {n}, CA {ca} vencido em {data} (validade {r['validade']})",
                                   "pedir nota fiscal ao RH"))
    return achados  # lista vazia = linha ok


def audita_funcionario(linhas: list[Linha], funcao: str) -> list[Achado]:
    """PROPOSTA (fora do contrato): regras que olham várias linhas juntas.

    EPI exigido ausente e troca fora da vida útil não cabem em audita_linha,
    que vê uma linha só. Combinar com o Gustavo no kickoff.
    """
    if not linhas:
        return []
    fid = linhas[0].get("funcionario_id", "?")
    exig = exigencia_funcao(funcao)
    if not exig.get("encontrada"):
        return [_achado(None, fid, "funcao_desconhecida", "risco", "corrigivel",
                        f"função '{funcao}' fora da tabela função → EPI", "revisar a função do funcionário")]
    achados: list[Achado] = []
    for e in exig["epis"]:
        entregas = sorted(l["data"] for l in linhas if l.get("data") and categoria_epi(l.get("epi")) == e["epi"])
        if not entregas:
            achados.append(_achado(None, fid, "epi_inadequado", "irregular", "corrigivel",
                                   f"nenhuma entrega de {e['epi']} na ficha; a função exige ({exig['agente_nocivo']})",
                                   f"entregar {e['epi']}, registrar com o CA e colher a assinatura"))
            continue
        datas = [date.fromisoformat(d) for d in entregas] + [date.today()]
        for a, b in zip(datas, datas[1:]):
            if (b - a).days > e["vida_util_dias"]:
                achados.append(_achado(None, fid, "troca_atrasada", "irregular", "corrigivel",
                                       f"{e['epi']}: {(b - a).days} dias entre {a} e {b}; vida útil {e['vida_util_dias']} dias",
                                       f"trocar {e['epi']} agora"))
                break
    return achados


SALARIO_MINIMO = 1621.00  # o mesmo do exposicao.py do Gustavo


def calcula_exposicao(achados: list[Achado], funcoes: dict[str, str] | None = None, hoje: date | None = None) -> dict[str, Any]:
    """Mesma assinatura do heitor/dados/exposicao.py real; grau fixo 0,20 e meses desde a data mais antiga."""
    hoje = hoje or date.today()
    passivos = [a for a in achados if a.get("tipo") == "passivo" and a.get("gravidade") != "ok"]
    funcionarios = sorted({a["funcionario_id"] for a in passivos})
    total = 0.0
    for fid in funcionarios:
        datas = sorted(str(a["data"]) for a in passivos if a["funcionario_id"] == fid and a.get("data"))
        if datas:
            d = date.fromisoformat(datas[0][:10])
            meses = (hoje.year - d.year) * 12 + hoje.month - d.month
        else:
            meses = 12
        total += 0.20 * SALARIO_MINIMO * min(max(meses, 0), 60)
    return {"total_brl": round(total, 2), "salario_minimo": SALARIO_MINIMO, "funcionarios": funcionarios,
            "descricao": "exposição potencial máxima, se a perícia confirmar a insalubridade"}


# ----------------------------------------------------------------- Pierre ---

_PENDENCIAS: dict[str, Pendencia] = {}
_ACHADOS_DAS_PENDENCIAS: dict[str, Achado] = {}
_ids_pend = itertools.count(1)


def criar_pendencia(achado: Achado, destino: str, acao: str, prazo: str) -> Pendencia:
    p: Pendencia = {"id": f"p-{next(_ids_pend)}", "achado_id": achado["id"],
                    "auditoria_id": achado.get("auditoria_id"), "funcionario_id": achado.get("funcionario_id"),
                    "destino": destino, "acao": acao, "motivo": achado.get("evidencia"), "prazo": prazo,
                    "status": "aberta", "historico": [{"status": "aberta", "ts": _agora(), "nota": None}]}
    _PENDENCIAS[p["id"]] = p
    _ACHADOS_DAS_PENDENCIAS[p["id"]] = achado
    return p


def fechar_pendencia(pendencia: Pendencia, resultado: str) -> Pendencia:
    p = _PENDENCIAS.get(pendencia["id"], pendencia)
    p["status"] = "fechada" if resultado == "confirmada" else "reaberta"
    p.setdefault("historico", []).append({"status": p["status"], "ts": _agora(), "nota": resultado})
    return p


def obter_pendencia(pendencia_id: str) -> tuple[Pendencia, Achado] | None:
    """PROPOSTA (fora do contrato): reauditar precisa da pendência e do achado dela."""
    if pendencia_id not in _PENDENCIAS:
        return None
    return _PENDENCIAS[pendencia_id], _ACHADOS_DAS_PENDENCIAS[pendencia_id]


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def prazo_padrao(dias: int = 5) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()
