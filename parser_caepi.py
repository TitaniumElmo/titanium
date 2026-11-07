import csv
import re
from collections import defaultdict
from datetime import datetime

CAMINHO = "dados/RelatorioCA_20261107_114519.csv"


def parse_data(texto):
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def data_da_base(caminho):
    achado = re.search(r"_(\d{8})_", caminho)
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


def resolver_ca(linhas):
    escolhida = max(linhas, key=lambda l: parse_data(l["DATA DE VALIDADE"]))
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


if __name__ == "__main__":
    base = carregar_base()
    print("data da base:", base["data_base"])
    print("registros:", len(base["registros"]))
    print("linhas quebradas:", len(base["quebrados"]))
    print("CAs unicos:", len(base["grupos"]))
    print("CAs conflitantes:", len(base["conflitantes"]))
    print(resolver_ca(base["grupos"]["7536"]))