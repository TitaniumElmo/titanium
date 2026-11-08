# Placeholder: mesma tabela do stub da Sofia (origin/agente). Gustavo confirma valores.
EXIGENCIA_PADRAO = {"agente_nocivo": "ruído", "grau": 0.20, "epis": {"protetor auditivo": 180}}
FUNCOES = {funcao: {**EXIGENCIA_PADRAO, "epis": dict(EXIGENCIA_PADRAO["epis"])}
           for funcao in ("pedreiro", "servente", "carpinteiro", "armador")}

# categorias que o código reconhece numa linha de ficha, exigidas ou não
CATEGORIAS_CONHECIDAS = ("protetor auditivo", "capacete", "calçado", "óculos", "luva")

SINONIMOS = {
    "protetor auricular": "protetor auditivo", "plug": "protetor auditivo", "abafador": "protetor auditivo",
    "bota": "calçado", "botina": "calçado", "sapato": "calçado",
    "luva": "luva", "oculos": "óculos", "óculos": "óculos",
}


def exigencia_funcao(funcao):
    f = FUNCOES.get((funcao or "").strip().lower())
    if not f:
        return {"funcao": funcao, "encontrada": False}
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
