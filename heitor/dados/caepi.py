"""Base CAEPI (Certificados de Aprovação de EPI, do MTE) e consulta de CA.

A base NÃO vai para o Git (144 MB, acima do limite do GitHub). Para testar:

1. Abra https://caepi.trabalho.gov.br/internet/consultacainternet.aspx
2. Clique em "Base de dados do sistema CAEPI (Download)". O site gera um
   arquivo RelatorioCA_<AAAAMMDD>_<HHMMSS>.csv (pode demorar uns minutos).
3. Coloque o arquivo, sem renomear, na pasta dados/ da raiz do projeto.
   Com mais de um, vale o mais recente.
4. Rode `pytest -q`. Sem a base, os testes que dependem dela são pulados
   ("CSV do CAEPI não está em dados/") e o consulta_ca avisa onde baixar.

A base é um retrato do dia do download: cada CA vem só com a validade atual,
sem histórico.
"""

import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

PASTA_DADOS = Path(__file__).resolve().parents[2] / "dados"
SITE_CAEPI = "https://caepi.trabalho.gov.br/internet/consultacainternet.aspx"


def base_mais_recente(pasta=PASTA_DADOS):
    """Download mais recente da base em dados/.

    O site do CAEPI gera um nome novo a cada download
    (RelatorioCA_<AAAAMMDD>_<HHMMSS>.csv); em ordem alfabética, o último é o
    mais novo. Sem nenhum arquivo, devolve um caminho que não existe.
    """
    arquivos = sorted(pasta.glob("RelatorioCA_*.csv"))
    return arquivos[-1] if arquivos else pasta / "RelatorioCA_AAAAMMDD_HHMMSS.csv"


CAMINHO = base_mais_recente()


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
    if not Path(caminho).exists():
        raise FileNotFoundError(
            f"base CAEPI não encontrada em {Path(caminho).parent}: baixe em {SITE_CAEPI} "
            "('Base de dados do sistema CAEPI (Download)') e coloque o RelatorioCA_*.csv em dados/"
        )
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


MAX_SUGESTOES = 5
DISTANCIA_MAXIMA = 2


def distancia_edicao(a, b, limite):
    """Levenshtein; devolve limite + 1 quando passa do limite."""
    if abs(len(a) - len(b)) > limite:
        return limite + 1
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        if min(atual) > limite:
            return limite + 1
        anterior = atual
    return anterior[-1]


def buscar_ca_proximo(numero):
    """Sugere CAs parecidos com um número digitado errado. So sugestao: confianca sempre baixa."""
    chave = str(numero).strip().lstrip("0") if numero is not None else ""
    if not chave or not chave.isdigit():
        return []
    grupos = base_padrao()["grupos"]
    if chave in grupos:
        return []

    achados = {1: [], 2: []}
    for candidato in grupos:
        if abs(len(candidato) - len(chave)) > DISTANCIA_MAXIMA:
            continue
        d = distancia_edicao(chave, candidato, DISTANCIA_MAXIMA)
        if d <= DISTANCIA_MAXIMA:
            achados[d].append(candidato)
    candidatos = achados[1] or achados[2]
    distancia = 1 if achados[1] else 2

    sugestoes = []
    for n in candidatos:
        r = resolver_ca(grupos[n])
        sugestoes.append({
            "numero": n,
            "equipamento": r["equipamento"],
            "validade": r["validade"].isoformat(),
            "situacao": r["registro"]["SITUACAO"].strip(),
            "distancia": distancia,
            "confianca": "baixa",
        })
    sugestoes.sort(key=lambda x: x["validade"], reverse=True)
    sugestoes.sort(key=lambda x: x["distancia"])
    return sugestoes[:MAX_SUGESTOES]


if __name__ == "__main__":
    base = carregar_base()
    print("data da base:", base["data_base"])
    print("registros:", len(base["registros"]))
    print("linhas quebradas:", len(base["quebrados"]))
    print("CAs unicos:", len(base["grupos"]))
    print("CAs conflitantes:", len(base["conflitantes"]))
    print(resolver_ca(base["grupos"]["7536"]))