import itertools
from datetime import date

from heitor.contrato import Achado, Linha
from heitor.dados.caepi import consulta_ca
from heitor.dados.funcoes import categoria_epi, exigencia_funcao

_ids = itertools.count(1)


def _achado(funcionario_id, linha, regra, gravidade, tipo, evidencia, acao):
    campos = dict(
        id=f"a-{next(_ids)}", funcionario_id=funcionario_id, linha=linha, regra=regra,
        gravidade=gravidade, tipo=tipo, evidencia=evidencia, acao_sugerida=acao,
    )
    if regra == "funcao_desconhecida":
        # ainda fora do Literal Regra do contrato (proposta): pula a validacao
        return Achado.model_construct(**campos)
    return Achado(**campos)


def _achados_de_ca(l):
    if not l.ca or not l.data:
        return []
    r = consulta_ca(l.ca, l.data)
    f, n, ca = l.funcionario_id, l.linha, l.ca
    achados = []
    if not r["encontrado"]:
        achados.append(_achado(f, n, "ca_nao_encontrado", "risco", "prova",
                               f"linha {n}, CA {ca} não está na base", "confirmar o CA com o RH"))
        return achados
    if r["conflito"]:
        achados.append(_achado(f, n, "ca_conflitante", "risco", "corrigivel",
                               f"linha {n}, CA {ca} com dados conflitantes na base", "técnico confere o CA"))
    if r["situacao"].upper() in ("CANCELADO", "SUSPENSO"):
        achados.append(_achado(f, n, "ca_cancelado", "risco", "corrigivel",
                               f"linha {n}, CA {ca} {r['situacao'].lower()} na base",
                               "revisar o CA e trocar o EPI se preciso"))
    elif not r["valido_na_data"]:
        achados.append(_achado(f, n, "ca_vencido", "risco", "prova",
                               f"linha {n}, CA {ca}: {r['motivo']}", "pedir nota fiscal ao RH"))
    return achados


def audita_linha(linha: Linha, funcao: str) -> list[Achado]:
    f, n = linha.funcionario_id, linha.linha
    achados = []
    if linha.assinatura is False:
        achados.append(_achado(f, n, "assinatura_ausente", "irregular", "passivo",
                               f"linha {n}, sem assinatura", "colher assinatura nas próximas entregas"))
    if not (linha.ca or "").strip():
        achados.append(_achado(f, n, "ca_ausente", "risco", "prova",
                               f"linha {n}, campo CA vazio", "pedir nota fiscal ao RH"))
    else:
        achados += _achados_de_ca(linha)
    return achados


def audita_funcionario(linhas: list[Linha], funcao: str, hoje=None) -> list[Achado]:
    if not linhas:
        return []
    hoje = hoje or date.today()
    fid = linhas[0].funcionario_id

    achados = []
    exig = exigencia_funcao(funcao)
    if not exig:
        achados.append(_achado(fid, None, "funcao_desconhecida", "risco", "corrigivel",
                               f"função '{funcao}' fora da tabela função → EPI",
                               "revisar a função do funcionário"))
        return achados

    exigidos = exig["epis"]
    entregas = {}
    for l in linhas:
        cat = categoria_epi(l.epi)
        if cat not in exigidos:
            achados.append(_achado(fid, l.linha, "epi_inadequado", "risco", "corrigivel",
                                   f"linha {l.linha}, '{l.epi}' não é exigido para {funcao}",
                                   "conferir se o EPI entregue é o certo para a função"))
        elif l.data:
            entregas.setdefault(cat, []).append(l.data)

    for cat, vida_util in exigidos.items():
        datas = sorted(entregas.get(cat, []))
        if not datas:
            achados.append(_achado(fid, None, "epi_inadequado", "irregular", "corrigivel",
                                   f"nenhuma entrega de {cat} na ficha; a função exige ({exig['agente_nocivo']})",
                                   f"entregar {cat}, registrar com o CA e colher a assinatura"))
            continue
        for a, b in zip(datas, datas[1:] + [hoje]):
            if (b - a).days > vida_util:
                achados.append(_achado(fid, None, "troca_atrasada", "irregular", "corrigivel",
                                       f"{cat}: {(b - a).days} dias entre {a} e {b}; vida útil {vida_util} dias",
                                       f"trocar {cat} agora"))
                break
    return achados
