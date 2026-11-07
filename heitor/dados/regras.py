import functools
import itertools
import re
from datetime import date

from heitor.contrato import Achado, Linha
from heitor.dados.caepi import consulta_ca
from heitor.dados.funcoes import categoria_epi, exigencia_funcao

_ids = itertools.count(1)

LIMITE_ASSINATURA = 0.7


def _achado(funcionario_id, linha, regra, gravidade, tipo, evidencia, acao):
    campos = dict(
        id=f"a-{next(_ids)}", funcionario_id=funcionario_id, linha=linha, regra=regra,
        gravidade=gravidade, tipo=tipo, evidencia=evidencia, acao_sugerida=acao,
    )
    if regra == "funcao_desconhecida":
        # ainda fora do Literal Regra do contrato (proposta): pula a validacao
        return Achado.model_construct(**campos)
    return Achado(**campos)


def _normaliza_ca(texto):
    return "".join(re.findall(r"\d", str(texto or "")))


def _achados_de_ca(l, ca):
    hoje = date.today()
    r = consulta_ca(ca, l.data or hoje)
    f, n = l.funcionario_id, l.linha
    if not r["encontrado"]:
        return [_achado(f, n, "ca_nao_encontrado", "risco", "prova",
                        f"linha {n}, CA {ca} não está na base", "confirmar o CA com o RH")]
    if r["conflito"]:
        return [_achado(f, n, "ca_conflitante", "risco", "corrigivel",
                        f"linha {n}, CA {ca} com dados conflitantes na base", "técnico confere o CA")]
    achados = []
    validade = date.fromisoformat(r["validade"])
    if l.data and l.data > validade:
        achados.append(_achado(f, n, "ca_vencido", "risco", "prova",
                               f"linha {n}, CA {ca}: venceu em {validade:%d/%m/%Y}, antes da entrega em {l.data:%d/%m/%Y}",
                               "pedir nota fiscal ao RH"))
    if r["situacao"].upper() in ("CANCELADO", "SUSPENSO"):
        achados.append(_achado(f, n, "ca_cancelado", "risco", "corrigivel",
                               f"linha {n}, CA {ca} {r['situacao'].lower()} na base",
                               "revisar o CA e trocar o EPI se preciso"))
    return achados


_OPCIONAIS_DO_ACHADO = ("auditoria_id", "norma", "exposicao_rs")


def _achado_para_dict(a):
    d = a.model_dump(mode="json")
    for k in _OPCIONAIS_DO_ACHADO:
        if d.get(k) is None:
            d.pop(k, None)
    return d


def _aceita_dict(funcao_real):
    """Entrada dict (agente) -> saida list[dict] no formato do stub; Linha -> list[Achado]."""
    @functools.wraps(funcao_real)
    def envelope(entrada, *args, **kwargs):
        if isinstance(entrada, list):
            como_dict = any(isinstance(l, dict) for l in entrada)
            linhas = [Linha.model_validate(l) if isinstance(l, dict) else l for l in entrada]
        else:
            como_dict = isinstance(entrada, dict)
            linhas = Linha.model_validate(entrada) if como_dict else entrada
        achados = funcao_real(linhas, *args, **kwargs)
        return [_achado_para_dict(a) for a in achados] if como_dict else achados
    return envelope


@_aceita_dict
def audita_linha(linha: Linha, funcao: str) -> list[Achado]:
    f, n = linha.funcionario_id, linha.linha
    achados = []
    conf = linha.confianca.get("assinatura", 1.0)
    if linha.assinatura is None or (linha.assinatura is False and conf < LIMITE_ASSINATURA):
        if "assinatura" in linha.confianca:
            evidencia = f"linha {n}, assinatura incerta na leitura (confiança {conf:.2f})"
        else:
            evidencia = f"linha {n}, assinatura não identificada na leitura"
        achados.append(_achado(f, n, "assinatura_ausente", "risco", "prova", evidencia,
                               "conferir a assinatura na ficha física"))
    elif linha.assinatura is False:
        achados.append(_achado(f, n, "assinatura_ausente", "irregular", "passivo",
                               f"linha {n}, sem assinatura", "colher assinatura nas próximas entregas"))
    ca = _normaliza_ca(linha.ca)
    if not ca:
        achados.append(_achado(f, n, "ca_ausente", "risco", "prova",
                               f"linha {n}, campo CA vazio", "pedir nota fiscal ao RH"))
    else:
        achados += _achados_de_ca(linha, ca)
    return achados


@_aceita_dict
def audita_funcionario(linhas: list[Linha], funcao: str, hoje=None) -> list[Achado]:
    if not linhas:
        return []
    hoje = hoje or date.today()
    fid = linhas[0].funcionario_id

    achados = []
    exig = exigencia_funcao(funcao)
    if not exig["encontrada"]:
        achados.append(_achado(fid, None, "funcao_desconhecida", "risco", "corrigivel",
                               f"função '{funcao}' fora da tabela função → EPI",
                               "revisar a função do funcionário"))
        return achados

    exigidos = {e["epi"]: e["vida_util_dias"] for e in exig["epis"]}
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
