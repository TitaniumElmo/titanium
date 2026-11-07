import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

CAMINHO = Path(__file__).resolve().parents[2] / "dados" / "RelatorioCA_20261107_114519.csv"


def parse_data(texto):
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def data_da_base(caminho):
    achado = re.search(r"_(\d{8})_", str(caminho))
    if not achado:
        return None
    return datetime.strptime(achado.group(1), "%Y%m%d").date()


def ler_base(caminho):
    validos, quebrados = [], []
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        leitor.fieldnames = [n.lstrip("\ufeff").strip() for n in leitor.fieldnames]
        for r in leitor:
            if None in r or None in r.values():
                quebrados.append(r)
                continue
            try:
                parse_data(r["DATA DE VALIDADE"])
            except ValueError:
                quebrados.append(r)
                continue
            validos.append(r)
    return validos, quebrados


def agrupar_por_ca(registros):
    grupos = defaultdict(list)
    for r in registros:
        grupos[r["NR Registro CA"].strip()].append(r)
    return grupos


def achar_conflitantes(grupos):
    conflitantes = {}
    for ca, linhas in grupos.items():
        versoes = {(l["DATA DE VALIDADE"], l["SITUACAO"]) for l in linhas}
        if len(versoes) > 1:
            conflitantes[ca] = sorted(versoes)
    return conflitantes


GRAVIDADE_SITUACAO = {"VÁLIDO": 0, "VENCIDO": 1, "SUSPENSO": 2, "CANCELADO": 3}


def _chave_resolucao(linha):
    pior = GRAVIDADE_SITUACAO.get(linha["SITUACAO"].strip().upper(), 0)
    return parse_data(linha["DATA DE VALIDADE"]), pior


def resolver_ca(linhas):
    escolhida = max(linhas, key=_chave_resolucao)
    versoes = {(l["DATA DE VALIDADE"], l["SITUACAO"]) for l in linhas}
    return {
        "ca": escolhida["NR Registro CA"].strip(),
        "validade": parse_data(escolhida["DATA DE VALIDADE"]),
        "equipamento": escolhida["EQUIPAMENTO"],
        "conflito": len(versoes) > 1,
        "registro": escolhida,
    }


def carregar_base(caminho=CAMINHO):
    registros, quebrados = ler_base(caminho)
    grupos = agrupar_por_ca(registros)
    return {
        "data_base": data_da_base(caminho),
        "registros": registros,
        "quebrados": quebrados,
        "grupos": grupos,
        "conflitantes": achar_conflitantes(grupos),
    }


SITUACOES_INVALIDAS = {"CANCELADO", "SUSPENSO"}


_base_cache = None


def base_padrao():
    global _base_cache
    if _base_cache is None:
        _base_cache = carregar_base()
    return _base_cache


def _como_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = valor.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return date.fromisoformat(texto)
    return parse_data(texto)


def consulta_ca(numero, data):
    chave = str(numero).strip()
    entrega = _como_data(data)
    linhas = base_padrao()["grupos"].get(chave)
    if not linhas:
        return {"numero": numero, "encontrado": False, "motivo": "CA nao existe na base"}

    r = resolver_ca(linhas)
    situacao = r["registro"]["SITUACAO"].strip()
    validade = r["validade"]

    if situacao.upper() in SITUACOES_INVALIDAS:
        motivo = f"CA {situacao.lower()}"
        valido = False
    elif validade >= entrega:
        motivo = f"validade {validade:%d/%m/%Y} cobre a entrega em {entrega:%d/%m/%Y}"
        valido = True
    else:
        motivo = f"venceu em {validade:%d/%m/%Y}, antes da entrega em {entrega:%d/%m/%Y}"
        valido = False
    if r["conflito"]:
        motivo += " (CA conflitante na base: conferir)"

    return {
        "numero": numero,
        "encontrado": True,
        "valido_na_data": valido,
        "validade": validade.isoformat(),
        "situacao": situacao,
        "equipamento": r["equipamento"],
        "conflito": r["conflito"],
        "motivo": motivo,
    }


if __name__ == "__main__":
    base = carregar_base()
    print("data da base:", base["data_base"])
    print("registros:", len(base["registros"]))
    print("linhas quebradas:", len(base["quebrados"]))
    print("CAs unicos:", len(base["grupos"]))
    print("CAs conflitantes:", len(base["conflitantes"]))
    print(resolver_ca(base["grupos"]["7536"]))