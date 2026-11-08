# Placeholder: mesma tabela do stub da Sofia (origin/agente). Gustavo confirma valores.
import os

EXIGENCIA_PADRAO = {"agente_nocivo": "ruído", "grau": 0.20, "epis": {"protetor auditivo": 180}}
FUNCOES = {funcao: {**EXIGENCIA_PADRAO, "epis": dict(EXIGENCIA_PADRAO["epis"])}
           for funcao in ("pedreiro", "servente", "carpinteiro", "armador")}

# categorias que o código reconhece numa linha de ficha, exigidas ou não
CATEGORIAS_CONHECIDAS = ("protetor auditivo", "capacete", "calçado", "óculos", "luva")

# PGR completo: so com HEITOR_PGR=completo. (vida util em dias, funcoes que exigem)
_TODAS = ("pedreiro", "servente", "carpinteiro", "armador")
_EPIS_PGR = {
    "protetor auditivo": (180, _TODAS),
    "capacete": (730, _TODAS),
    "calçado": (365, _TODAS),
    "óculos": (365, ("pedreiro", "carpinteiro")),
    "luva": (90, ("pedreiro", "servente", "armador")),
}
FUNCOES_PGR = {
    funcao: {"agente_nocivo": "ruído", "grau": 0.20,
             "epis": {epi: dias for epi, (dias, quem) in _EPIS_PGR.items() if funcao in quem}}
    for funcao in _TODAS
}


def pgr_completo():
    return os.environ.get("HEITOR_PGR") == "completo"


def agente_da_categoria(categoria):
    return "ruído" if categoria == "protetor auditivo" else "acidente"


SINONIMOS = {
    "protetor auricular": "protetor auditivo", "plug": "protetor auditivo", "abafador": "protetor auditivo",
    "bota": "calçado", "botina": "calçado", "sapato": "calçado",
    "luva": "luva", "oculos": "óculos", "óculos": "óculos",
}


def exigencia_funcao(funcao):
    pgr = pgr_completo()
    f = (FUNCOES_PGR if pgr else FUNCOES).get((funcao or "").strip().lower())
    if not f:
        return {"funcao": funcao, "encontrada": False}
    if pgr:
        return {
            "funcao": funcao, "encontrada": True,
            "agente_nocivo": f["agente_nocivo"], "grau": f["grau"],
            "epis": [{"epi": epi, "vida_util_dias": dias, "agente_nocivo": agente_da_categoria(epi)}
                     for epi, dias in f["epis"].items()],
        }
    return {
        "funcao": funcao, "encontrada": True,
        "agente_nocivo": f["agente_nocivo"], "grau": f["grau"],
        "epis": [{"epi": epi, "vida_util_dias": dias} for epi, dias in f["epis"].items()],
    }


def categoria_epi(nome):
    n = (nome or "").strip().lower()
    if not n:
        return None
    for chave, cat in SINONIMOS.items():
        if chave in n:
            return cat
    for cat in CATEGORIAS_CONHECIDAS:
        if cat in n:
            return cat
    return n
