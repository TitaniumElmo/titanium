import functools
import inspect
import itertools
import re
from datetime import date

from heitor.contrato import Achado, Linha
from heitor.dados.caepi import consulta_ca
from heitor.dados.funcoes import categoria_epi, exigencia_funcao

_ids = itertools.count(1)

LIMITE_ASSINATURA = 0.7
REGRAS_FORA_DO_CONTRATO = {"funcao_desconhecida", "entrega_sem_ficha", "ficha_sem_planilha"}
CAMPOS_EXTRAS = ("na_ficha", "assinatura_tipo", "assinatura_texto", "leitura_assinatura", "conferencia_ca")
TIPOS_ASSINATURA_DUVIDOSA = {
    "texto": "na coluna de assinatura há texto{t}, não uma assinatura",
    "marca": "na coluna de assinatura há só uma marca{t}",
    "iniciais": "assinatura só com iniciais{t}",
    "outro_nome": "assinado{t}, nome diferente do funcionário",
    "ilegivel": "assinatura ilegível{t}",
}


def _achado(funcionario_id, linha, regra, gravidade, tipo, evidencia, acao):
    campos = dict(
        id=f"a-{next(_ids)}", funcionario_id=funcionario_id, linha=linha, regra=regra,
        gravidade=gravidade, tipo=tipo, evidencia=evidencia, acao_sugerida=acao,
    )
    if regra in REGRAS_FORA_DO_CONTRATO:
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
    recebe_extras = "extras" in inspect.signature(funcao_real).parameters

    @functools.wraps(funcao_real)
    def envelope(entrada, *args, **kwargs):
        if recebe_extras and isinstance(entrada, dict):
            kwargs["extras"] = {k: entrada.get(k) for k in CAMPOS_EXTRAS}
        if isinstance(entrada, list):
            como_dict = any(isinstance(l, dict) for l in entrada)
            linhas = [Linha.model_validate(l) if isinstance(l, dict) else l for l in entrada]
        else:
            como_dict = isinstance(entrada, dict)
            linhas = Linha.model_validate(entrada) if como_dict else entrada
        achados = funcao_real(linhas, *args, **kwargs)
        return [_achado_para_dict(a) for a in achados] if como_dict else achados
    return envelope


def _achados_de_assinatura(linha, extras):
    f, n = linha.funcionario_id, linha.linha
    tipo, texto, na_ficha = extras.get("assinatura_tipo"), extras.get("assinatura_texto"), extras.get("na_ficha")

    if na_ficha is False or tipo == "sem_linha_na_ficha":
        data = f"{linha.data:%d/%m/%Y}" if linha.data else "data não lida"
        return [_achado(f, n, "entrega_sem_ficha", "risco", "prova",
                        f"linha {n}, entrega de {linha.epi} ({data}) registrada na planilha sem linha na ficha de papel; "
                        "falta a prova da entrega; conferir",
                        "conferir a ficha de papel")]
    if tipo in TIPOS_ASSINATURA_DUVIDOSA:
        citado = f" '{texto}'" if texto else ""
        return [_achado(f, n, "assinatura_ausente", "risco", "prova",
                        f"linha {n}, {TIPOS_ASSINATURA_DUVIDOSA[tipo].format(t=citado)}; conferir",
                        "conferir a assinatura na ficha física")]
    if tipo == "nome_confere":
        return []

    conf = linha.confianca.get("assinatura", 1.0)
    if linha.assinatura is None or (linha.assinatura is False and conf < LIMITE_ASSINATURA):
        if "assinatura" in linha.confianca:
            evidencia = f"linha {n}, assinatura incerta na leitura (confiança {conf:.2f})"
        else:
            evidencia = f"linha {n}, assinatura não identificada na leitura"
        return [_achado(f, n, "assinatura_ausente", "risco", "prova", evidencia,
                        "conferir a assinatura na ficha física")]
    if linha.assinatura is False:
        return [_achado(f, n, "assinatura_ausente", "irregular", "passivo",
                        f"linha {n}, sem assinatura", "colher assinatura nas próximas entregas")]
    return []


@_aceita_dict
def audita_linha(linha: Linha, funcao: str, extras: dict | None = None) -> list[Achado]:
    f, n = linha.funcionario_id, linha.linha
    achados = _achados_de_assinatura(linha, extras or {})
    ca = _normaliza_ca(linha.ca)
    conferencia = (extras or {}).get("conferencia_ca")
    if ca and conferencia and conferencia.get("confere") is False:
        # leitura duvidosa do CA nunca vira CA vencido
        motivo = conferencia.get("motivo") or "CA não confere com a ficha"
        achados.append(_achado(f, n, "ca_nao_encontrado", "risco", "prova",
                               f"linha {n}, {motivo}", "conferir o CA na ficha física"))
        return achados
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


def audita_fora_da_planilha(itens, funcionario_id):
    """Linhas do papel sem entrega na planilha. itens = [{"data": "AAAA-MM-DD", "epi": "..."}]."""
    if isinstance(itens, dict):
        itens = [itens]
    achados = []
    for item in itens or []:
        d = item.get("data")
        try:
            d = f"{date.fromisoformat(str(d)[:10]):%d/%m/%Y}"
        except ValueError:
            pass
        achados.append(_achado(
            funcionario_id, None, "ficha_sem_planilha", "risco", "corrigivel",
            f"A ficha de papel mostra {item.get('epi')} em {d} que não está na planilha de controle; "
            "leitura aberta do papel pode errar; conferir",
            "conferir a ficha de papel e a planilha de controle"))
    return [_achado_para_dict(a) for a in achados]
