from datetime import date

from heitor.dados.funcoes import exigencia_funcao, pgr_completo

SALARIO_MINIMO = 1621.00
GRAUS_VALIDOS = (0.10, 0.20, 0.40)
GRAU_PADRAO = 0.20
TETO_MESES = 60
MESES_SEM_DATA = 12
DESCRICAO = "exposição potencial máxima, se a perícia confirmar a insalubridade"


def _como_dict(achado):
    return achado if isinstance(achado, dict) else achado.model_dump(mode="json")


def _data_do_achado(a):
    valor = a.get("data") or a.get("data_entrega")
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _meses_entre(inicio, hoje):
    meses = (hoje.year - inicio.year) * 12 + (hoje.month - inicio.month)
    if hoje.day < inicio.day:
        meses -= 1
    return max(meses, 0)


def _grau_da_funcao(funcao):
    exig = exigencia_funcao(funcao)
    if not exig["encontrada"]:
        return GRAU_PADRAO, f"função '{funcao}' desconhecida: grau {GRAU_PADRAO:.2f} assumido"
    grau = exig.get("grau")
    if grau not in GRAUS_VALIDOS:
        return GRAU_PADRAO, f"grau da função '{funcao}' não informado: {GRAU_PADRAO:.2f} assumido"
    return grau, None


def calcula_exposicao(achados, funcoes=None, hoje=None):
    """funcoes: {funcionario_id: funcao}. Sem isso, usa a chave 'funcao' do achado (se houver)."""
    hoje = hoje or date.today()
    funcoes = funcoes or {}
    passivos = [_como_dict(a) for a in achados]
    passivos = [a for a in passivos if a.get("tipo") == "passivo" and a.get("gravidade") != "ok"]
    if pgr_completo():
        passivos = [a for a in passivos if a.get("agente_nocivo") == "ruído"]

    por_func = {}
    for a in passivos:
        fid = a["funcionario_id"]
        d = _data_do_achado(a)
        meses = _meses_entre(d, hoje) if d else MESES_SEM_DATA
        item = por_func.setdefault(fid, {"meses": 0, "estimados": True, "funcao": None})
        if d and (item["estimados"] or meses > item["meses"]):
            item.update(meses=meses, estimados=False)
        elif d is None and item["estimados"]:
            item["meses"] = max(item["meses"], meses)
        item["funcao"] = item["funcao"] or funcoes.get(fid) or a.get("funcao")

    detalhe, avisos = {}, []
    for fid in sorted(por_func):
        item = por_func[fid]
        grau, aviso = _grau_da_funcao(item["funcao"])
        if aviso:
            avisos.append(f"funcionário {fid}: {aviso}")
        meses = min(item["meses"], TETO_MESES)
        detalhe[fid] = {
            "grau": grau, "meses": meses,
            "valor_brl": round(grau * SALARIO_MINIMO * meses * 1, 2),
        }
        if item["estimados"]:
            detalhe[fid]["meses_estimados"] = True

    resultado = {
        "total_brl": round(sum(d["valor_brl"] for d in detalhe.values()), 2),
        "salario_minimo": SALARIO_MINIMO,
        "funcionarios": sorted(detalhe),
        "descricao": DESCRICAO,
        "por_funcionario": detalhe,
    }
    if any(d.get("meses_estimados") for d in detalhe.values()):
        resultado["meses_estimados"] = True
    if avisos:
        resultado["avisos"] = avisos
    return resultado
