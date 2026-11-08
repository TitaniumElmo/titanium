"""Extração: planilha (CSV ou linhas do Google Sheets) -> list[Linha].

mapear_colunas descobre qual coluna é data, EPI, CA, assinatura etc.:
  1. o LLM propõe o mapeamento olhando o cabeçalho e uma amostra;
  2. o código confere o CONTEÚDO de cada coluna proposta (datas parecem datas?);
  3. sem LLM, uma heurística por palavras-chave faz o mapeamento.
Campo com confiança < 0.7 fica marcado como baixa confiança, nunca é chutado.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

from heitor.agente.ferramentas import normalizar_ca, normalizar_data
from heitor.agente.llm import ClienteLLM, LLMIndisponivel, extrair_json, llm_ligado
from heitor.agente.tipos import LinhaDict as Linha

CAMPOS = ("funcionario_id", "nome", "funcao", "data", "epi", "qtd", "ca", "motivo", "assinatura")
LIMIAR_CONFIANCA = 0.7

_DESCRICAO_CAMPOS = {
    "funcionario_id": "matrícula ou código do funcionário",
    "nome": "nome do funcionário",
    "funcao": "função ou cargo",
    "data": "data da entrega do EPI",
    "epi": "nome ou descrição do EPI entregue",
    "qtd": "quantidade entregue",
    "ca": "número do Certificado de Aprovação (CA)",
    "motivo": "motivo da entrega (primeira entrega, troca, perda...)",
    "assinatura": "se o funcionário assinou (sim/não, x, assinado...)",
}

# Rótulo curto de cada campo, para a tela (tabela de colunas em Fontes).
ROTULO_CAMPO = {
    "funcionario_id": "Matrícula", "nome": "Nome", "funcao": "Função", "data": "Data da entrega", "epi": "EPI",
    "qtd": "Quantidade", "ca": "Nº do CA", "motivo": "Motivo", "assinatura": "Assinatura",
}

_PALAVRAS: dict[str, tuple[str, ...]] = {
    "funcionario_id": ("matricula", "mat", "codigo", "cod", "id", "registro", "chapa", "re"),
    "nome": ("nome", "funcionario", "colaborador", "empregado", "trabalhador"),
    "funcao": ("funcao", "cargo", "ocupacao", "atividade"),
    "data": ("data", "dt", "dia", "entrega", "entregue"),
    "epi": ("epi", "equipamento", "item", "descricao", "material", "produto"),
    "qtd": ("qtd", "qtde", "quantidade", "quant", "qt"),
    "ca": ("ca", "c.a", "certificado", "n ca", "no ca", "num ca", "numero ca"),
    "motivo": ("motivo", "tipo", "razao"),
    "assinatura": ("assinatura", "ass", "assinado", "visto", "rubrica", "recebido"),
}

_SIM = {"sim", "s", "x", "ok", "assinado", "assinou", "true", "1", "v", "yes", "y", "✓", "✔"}
_NAO = {"nao", "n", "false", "0", "", "-", "pendente", "sem", "no", "não"}


def _norm(texto: Any) -> str:
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9.]+", " ", s).strip()


# ------------------------------------------------- conferência de conteúdo ---

def _fracao(valores: list[str], teste) -> float:
    preenchidos = [v for v in valores if str(v).strip()]
    if not preenchidos:
        return 0.0
    return sum(1 for v in preenchidos if teste(v)) / len(preenchidos)


def conferir_conteudo(campo: str, valores: list[str]) -> float:
    """De 0 a 1: quanto o conteúdo da coluna combina com o campo."""
    if campo == "data":
        return _fracao(valores, lambda v: normalizar_data(v) is not None)
    if campo == "ca":
        return _fracao(valores, lambda v: bool(re.fullmatch(r"\s*(ca\s*)?\d{3,6}\s*", _norm(v))))
    if campo == "qtd":
        return _fracao(valores, lambda v: bool(re.fullmatch(r"\s*\d{1,3}\s*", str(v))))
    if campo == "assinatura":
        return 1.0 if all(_norm(v) in _SIM | _NAO for v in valores) else 0.3
    if campo in ("nome", "epi", "funcao", "motivo"):
        return _fracao(valores, lambda v: bool(re.search(r"[a-zA-ZÀ-ú]{2,}", str(v)))
                       and normalizar_data(v) is None)
    if campo == "funcionario_id":
        return _fracao(valores, lambda v: bool(re.fullmatch(r"[\w.-]{1,12}", str(v).strip())))
    return 0.5


# ------------------------------------------------------------ heurística ---

def _mapear_heuristica(cabecalho: list[str], amostra: list[list[str]]) -> dict[str, dict[str, Any]]:
    colunas = {i: [linha[i] if i < len(linha) else "" for linha in amostra] for i in range(len(cabecalho))}
    candidatos = []
    for campo, palavras in _PALAVRAS.items():
        for i, nome in enumerate(cabecalho):
            n = _norm(nome)
            tokens = set(n.split()) | {t.strip(".") for t in n.split()}  # "Ass." e "Qtd." abreviados com ponto
            nome_bate = (n in palavras or n.strip(".") in palavras or bool(tokens & set(palavras))
                         or any(p in n for p in palavras if len(p) > 3))
            if not nome_bate:
                continue
            conteudo = conferir_conteudo(campo, colunas[i])
            exato = 0.15 if (n in palavras or n.strip(".") in palavras) else 0.0
            candidatos.append((0.5 + 0.35 * conteudo + exato, campo, i))
    return _resolver(candidatos, cabecalho, "heuristica")


def _resolver(candidatos: list[tuple[float, str, int]], cabecalho: list[str], origem: str) -> dict[str, dict]:
    """Cada campo fica com uma coluna e cada coluna com um campo (melhor nota primeiro)."""
    usados_campo: set[str] = set()
    usadas_col: set[int] = set()
    mapa: dict[str, dict[str, Any]] = {}
    for nota, campo, i in sorted(candidatos, reverse=True):
        if campo in usados_campo or i in usadas_col:
            continue
        mapa[campo] = {"coluna": cabecalho[i], "indice": i, "confianca": round(min(nota, 1.0), 2), "origem": origem}
        usados_campo.add(campo)
        usadas_col.add(i)
    return mapa


# ------------------------------------------------------------------- LLM ---

def _prompt_mapeamento(cabecalho: list[str], amostra: list[list[str]]) -> list[dict[str, str]]:
    campos = "\n".join(f"- {c}: {d}" for c, d in _DESCRICAO_CAMPOS.items())
    # Coluna por coluna: com cabeçalhos sem sentido ("Col A"), o modelo devolvia
    # valores de célula no lugar do nome da coluna quando via a planilha em linhas.
    colunas = "\n".join(
        f'- coluna "{nome}": exemplos {[l[i] for l in amostra if i < len(l) and str(l[i]).strip()][:4]}'
        for i, nome in enumerate(cabecalho))
    nomes = ", ".join(f'"{c}"' for c in cabecalho)
    return [
        {"role": "system", "content":
            "Você mapeia colunas de planilhas de controle de entrega de EPI. Responda SOMENTE com JSON."},
        {"role": "user", "content":
            f"Campos possíveis:\n{campos}\n\nColunas da planilha (nome e exemplos de valores):\n{colunas}\n\n"
            "Decida pelo CONTEÚDO dos exemplos, não só pelo nome. Números de CA têm de 3 a 6 dígitos.\n"
            f'Responda {{"<campo>": {{"coluna": <um destes nomes: {nomes}, ou null>, "confianca": <0 a 1>}}}} '
            "para cada campo. O valor de \"coluna\" é sempre o NOME da coluna, nunca um valor de célula. "
            "Use null quando nenhuma coluna corresponder. Não repita colunas."},
    ]


def _mapear_llm(cabecalho: list[str], amostra: list[list[str]], cliente: ClienteLLM) -> tuple[dict, float]:
    resp = cliente.completar(_prompt_mapeamento(cabecalho, amostra), max_tokens=600)
    bruto = extrair_json(resp.texto)
    indice = {c.strip(): i for i, c in enumerate(cabecalho)}
    colunas = {i: [linha[i] if i < len(linha) else "" for linha in amostra] for i in range(len(cabecalho))}
    candidatos = []
    for campo in CAMPOS:
        item = bruto.get(campo) or {}
        nome = item.get("coluna") if isinstance(item, dict) else None
        if not nome or str(nome).strip() not in indice:
            continue  # coluna inventada pelo LLM é descartada
        i = indice[str(nome).strip()]
        try:
            conf_llm = float(item.get("confianca", 0.8))
        except (TypeError, ValueError):
            conf_llm = 0.8
        conteudo = conferir_conteudo(campo, colunas[i])
        # O conteúdo tem a palavra final: LLM confiante numa coluna que não combina vira baixa confiança.
        candidatos.append((min(max(0.0, min(conf_llm, 1.0)), 0.3 + 0.7 * conteudo), campo, i))
    return _resolver(candidatos, cabecalho, "llm"), resp.custo_usd


def mapear_colunas(cabecalho: list[str], amostra: list[list[str]]) -> dict[str, Any]:
    """Descobre qual coluna é cada campo. Ferramenta do agente (dona: Sofia).

    Devolve {"mapeamento": {campo: {coluna, indice, confianca, origem}},
             "nao_mapeados": [...], "baixa_confianca": [...], "custo_usd": float, "origem": "llm"|"heuristica"}
    """
    cabecalho = [str(c).strip() for c in cabecalho]
    amostra = [list(map(str, l)) for l in amostra[:8]]
    heur = _mapear_heuristica(cabecalho, amostra)
    mapa, custo, origem = heur, 0.0, "heuristica"
    if llm_ligado():
        try:
            llm_mapa, custo = _mapear_llm(cabecalho, amostra, ClienteLLM())
            mapa, origem = _combinar(llm_mapa, heur), "llm"
        except (LLMIndisponivel, ValueError):
            pass
    return {
        "mapeamento": mapa,
        "colunas": tabela_de_colunas(cabecalho, amostra, mapa),
        "nao_mapeados": [c for c in CAMPOS if c not in mapa],
        "baixa_confianca": [c for c, m in mapa.items() if m["confianca"] < LIMIAR_CONFIANCA],
        "custo_usd": custo,
        "origem": origem,
    }


def tabela_de_colunas(cabecalho: list[str], amostra: list[list[str]], mapa: dict[str, dict]) -> list[dict[str, Any]]:
    """Uma linha por coluna da planilha, na ordem da planilha (para a tela de Fontes).

    [{"indice", "coluna", "campo", "campo_rotulo", "confianca", "origem", "exemplo", "situacao"}]
    situacao: "entendida" | "conferir" (confiança baixa) | "ignorada" (o Heitor não usa esta coluna).
    """
    por_indice = {m["indice"]: (campo, m) for campo, m in mapa.items()}
    tabela = []
    for i, nome in enumerate(cabecalho):
        exemplo = next((str(l[i]).strip() for l in amostra if i < len(l) and str(l[i]).strip()), "")
        campo, m = por_indice.get(i, (None, {}))
        conf = m.get("confianca")
        tabela.append({
            "indice": i, "coluna": nome, "campo": campo, "campo_rotulo": ROTULO_CAMPO.get(campo or "", None),
            "confianca": round(conf, 2) if conf is not None else None, "origem": m.get("origem"),
            "exemplo": exemplo[:40],
            "situacao": "ignorada" if campo is None else ("conferir" if conf < LIMIAR_CONFIANCA else "entendida"),
        })
    return tabela


def _combinar(llm: dict[str, dict], heur: dict[str, dict]) -> dict[str, dict]:
    """LLM e heurística concordando sobem a confiança; o LLM completa o que a heurística não achou e vice-versa."""
    final: dict[str, dict] = {}
    for campo in CAMPOS:
        a, b = llm.get(campo), heur.get(campo)
        if a and b and a["indice"] == b["indice"]:
            final[campo] = {**a, "confianca": round(max(a["confianca"], b["confianca"], 0.9), 2), "origem": "llm+heuristica"}
        elif a:
            final[campo] = a
        elif b and b["indice"] not in {m["indice"] for m in final.values()} | {m["indice"] for m in llm.values()}:
            final[campo] = b
    return final


# --------------------------------------------------------------- extração ---

def _assinatura(valor: str) -> tuple[bool | None, float]:
    v = _norm(valor)
    if v in _SIM:
        return True, 1.0
    if v in _NAO:
        return False, 1.0
    return (True, 0.6) if len(v) > 2 else (None, 0.0)  # rubrica escrita à mão vira "assinou", com dúvida


def extrair_linhas(cabecalho: list[str], linhas: list[list[str]], origem: str,
                   padrao: dict[str, Any] | None = None, mapeamento: dict[str, Any] | None = None) -> dict[str, Any]:
    """Converte linhas cruas em Linha. Usado pelo CSV e pelas linhas do Google Sheets (ler_fonte)."""
    mapeamento = mapeamento or mapear_colunas(cabecalho, linhas[:8])
    mapa = mapeamento["mapeamento"]
    padrao = padrao or {}
    saida: list[Linha] = []
    for n, crua in enumerate(linhas, start=1):
        if not any(str(c).strip() for c in crua):
            continue

        def valor(campo: str) -> str:
            m = mapa.get(campo)
            return str(crua[m["indice"]]).strip() if m and m["indice"] < len(crua) else ""

        conf: dict[str, float] = {c: m["confianca"] for c, m in mapa.items()}
        data = normalizar_data(valor("data"))
        if valor("data") and not data:
            conf["data"] = 0.3
        ca = normalizar_ca(valor("ca")) if valor("ca") else None
        assinatura, conf_ass = _assinatura(valor("assinatura")) if "assinatura" in mapa else (None, 0.0)
        conf["assinatura"] = round(conf.get("assinatura", 0.0) * conf_ass, 2)
        try:
            qtd = int(valor("qtd")) if valor("qtd") else None
        except ValueError:
            qtd = None
        fid, nome = valor("funcionario_id"), valor("nome")
        if not data and not valor("epi") and re.search(r"[,;\t|]", fid):
            # Linha colada sem dividir em colunas ("301,João Silva,servente,..." tudo na coluna A): recupera só
            # a matrícula e o nome. O agente vê a linha sem data e sem EPI e manda revisar, sem acusar nada.
            partes = [p.strip() for p in re.split(r"[,;\t|]", fid)]
            fid, nome = partes[0], nome or (partes[1] if len(partes) > 1 else "")
            conf["linha"] = 0.0
        saida.append({
            "funcionario_id": fid or str(padrao.get("funcionario_id", "?")),
            "nome": nome or padrao.get("nome", ""),
            "funcao": (valor("funcao") or padrao.get("funcao", "")).lower(),
            "linha": n, "data": data, "epi": valor("epi"), "qtd": qtd if qtd is not None else 1, "ca": ca,
            "motivo": valor("motivo") or None, "assinatura": assinatura,
            "confianca": conf, "origem": origem,
        })
    return {"linhas": saida, "mapeamento": mapeamento}


def _ler_csv(caminho: Path) -> tuple[list[str], list[list[str]]]:
    bruto = caminho.read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialeto = csv.Sniffer().sniff(texto[:2048], delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
    linhas = [l for l in csv.reader(io.StringIO(texto), dialeto)]
    return linhas[0], linhas[1:]


def extrair_ficha(arquivo: str, padrao: dict[str, Any] | None = None) -> dict[str, Any]:
    """Lê um arquivo de ficha e devolve {"linhas": list[Linha], "mapeamento": ...}. Ferramenta do agente.

    padrao: funcionario_id/nome/funcao para fichas de um funcionário só, em que
    esses dados ficam no topo da folha e não numa coluna.
    """
    caminho = Path(arquivo)
    sufixo = caminho.suffix.lower()
    if sufixo in (".csv", ".txt"):
        cabecalho, linhas = _ler_csv(caminho)
        return extrair_linhas(cabecalho, linhas, caminho.name, padrao)
    if sufixo in (".jpg", ".jpeg", ".png", ".webp"):
        from heitor.agente.foto import ler_foto

        r = ler_foto(caminho)
        return {"linhas": r["linhas"], "mapeamento": {"origem": "foto", "modelo": r["modelo"],
                                                      "cabecalho": r["cabecalho"], "custo_usd": r["custo_usd"]}}
    if sufixo == ".pdf":
        return _ler_pdf(caminho)
    raise ValueError(f"formato não suportado: {sufixo}")


MAX_PAGINAS_PDF = 4


def paginas_do_pdf(caminho: Path, max_paginas: int = MAX_PAGINAS_PDF) -> list[Path]:
    """Cada página vira um PNG ao lado do PDF (ficha escaneada ou planilha exportada: a leitura é a da foto)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(caminho))
    try:
        saida = []
        for i in range(min(len(pdf), max_paginas)):
            png = caminho.with_name(f"{caminho.stem}_p{i + 1}.png")
            pdf[i].render(scale=2).to_pil().save(png)  # ~144 dpi: o bastante para o modelo de visão
            saida.append(png)
        return saida
    finally:
        pdf.close()


def _ler_pdf(caminho: Path) -> dict[str, Any]:
    """PDF (o RH pode mandar a ficha arquivada assim): lê página por página como foto.

    Documento que não é ficha (nota fiscal, lista de presença) volta sem linhas; a reauditoria
    então deixa a pendência para conferência humana em vez de reabrir.
    """
    from heitor.agente.foto import ler_foto

    linhas: list[Linha] = []
    cabecalho: dict[str, Any] = {}
    custo, modelo = 0.0, None
    paginas = paginas_do_pdf(caminho)
    for png in paginas:
        r = ler_foto(png)
        custo += r["custo_usd"]
        modelo = modelo or r["modelo"]
        cabecalho = cabecalho or r["cabecalho"]
        for l in r["linhas"]:
            if linhas and l["funcionario_id"] == png.stem:  # página sem cabeçalho: continua a ficha anterior
                l.update({k: linhas[0][k] for k in ("funcionario_id", "nome", "funcao")})
            l["linha"] = len(linhas) + 1
            linhas.append(l)
    return {"linhas": linhas, "mapeamento": {"origem": "pdf", "modelo": modelo, "cabecalho": cabecalho,
                                             "custo_usd": round(custo, 6), "paginas": len(paginas)}}


def reextrair_campo(arquivo: str, linha: int, campo: str, dados: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Nova tentativa num campo de baixa confiança. Hoje: assinatura em foto.

    Devolve {"valor": ..., "confianca": float} ou None se não houver como reler.
    """
    from heitor.agente.foto import caminho_da_origem, reextrair_assinatura

    caminho = caminho_da_origem(arquivo)
    if not caminho or campo != "assinatura" or dados is None:
        return None
    return reextrair_assinatura(caminho, dados)
