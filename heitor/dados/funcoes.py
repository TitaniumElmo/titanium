# Placeholder: mesma tabela do stub da Sofia (origin/agente). Gustavo confirma valores.
FUNCOES = {
    "pedreiro": {"agente_nocivo": "ruído", "grau": 0.20,
                 "epis": {"protetor auditivo": 90, "capacete": 730, "calçado": 180}},
    "servente": {"agente_nocivo": "ruído", "grau": 0.20,
                 "epis": {"protetor auditivo": 90, "capacete": 730, "calçado": 180}},
    "carpinteiro": {"agente_nocivo": "ruído", "grau": 0.20,
                    "epis": {"protetor auditivo": 90, "óculos": 365}},
    "armador": {"agente_nocivo": "ruído", "grau": 0.20,
                "epis": {"protetor auditivo": 90, "luva": 30}},
}

SINONIMOS = {
    "protetor auricular": "protetor auditivo", "plug": "protetor auditivo", "abafador": "protetor auditivo",
    "bota": "calçado", "botina": "calçado", "sapato": "calçado",
    "luva": "luva", "oculos": "óculos", "óculos": "óculos",
}


def exigencia_funcao(funcao):
    return FUNCOES.get((funcao or "").strip().lower())


def categoria_epi(nome):
    n = (nome or "").strip().lower()
    if not n:
        return None
    for chave, cat in SINONIMOS.items():
        if chave in n:
            return cat
    for cat in {c for f in FUNCOES.values() for c in f["epis"]}:
        if cat in n:
            return cat
    return n
