"""Leitura de foto de ficha de EPI com modelo de visão (Qwen3-VL-32B no Featherless).

A assinatura é o campo mais difícil: a ficha inteira é manuscrita, e um
detector de "assinatura" (YOLO) confunde qualquer letra cursiva com rubrica.
Por isso a pergunta é feita duas vezes, de jeitos diferentes:

  A) leitura da tabela inteira, com a coluna Assinatura de cada linha;
  B) uma lista só da coluna Assinatura, com "vazio" como resposta explícita.

Concordaram -> confiança alta. Discordaram -> baixa confiança, e o agente
reextrai ou pede revisão.

Testado e descartado: perguntar linha por linha ("a célula DESTA linha tem
rubrica?"). O modelo tende a dizer "sim" e chegou a transcrever um nome numa
célula em branco. Listar a coluna inteira com a opção "vazio" errou menos.
"""

from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path
from typing import Any

from heitor.agente.assinatura import EFEITO as EFEITO_ASSINATURA
from heitor.agente.assinatura import classificar_linhas as classificar_assinaturas
from heitor.agente.conferencia_ca import aplicar as conferir_ca
from heitor.agente.conferencia_datas import aplicar as conferir_datas
from heitor.agente.ferramentas import normalizar_ca, normalizar_data
from heitor.agente.llm import ClienteLLM, extrair_json
from heitor.agente.tipos import LinhaDict

# Qwen2.5-VL-72B venceu a comparação de 7 modelos (13 fotos, 102 linhas; fotos_teste/resultados).
MODELO_VISAO = os.getenv("HEITOR_MODELO_VISAO", "Qwen/Qwen2.5-VL-72B-Instruct")
MODELO_VISAO_RESERVA = os.getenv("HEITOR_MODELO_VISAO_RESERVA", "Qwen/Qwen3-VL-32B-Instruct")
LADO_MAX = 1600  # px; maior que isso só deixa a chamada mais lenta

CONF_CONCORDA = 0.95
CONF_DISCORDA = 0.4
CONF_SO_UMA = 0.5

PROMPT_LEITURA = """Esta é a foto de uma ficha de entrega de EPI, provavelmente escrita à mão.
Leia o cabeçalho e TODAS as linhas de entrega da tabela, de cima para baixo.

Para cada campo de uma linha:
- escreva o valor lido;
- use "vazio" se a célula está em branco;
- use "ilegivel" se há escrita mas você não consegue ler.

assinatura: true se a coluna Assinatura DAQUELA linha tem assinatura ou rubrica, false se está em branco.
Cuidado: a foto pode estar inclinada e uma assinatura pode invadir a linha vizinha.

Responda SOMENTE com JSON:
{"cabecalho": {"nome": "...", "matricula": "...", "funcao": "...", "data_admissao": "DD/MM/AAAA"},
 "linhas": [{"data": "DD/MM/AAAA", "epi": "...", "ca": "...", "qtd": "...", "motivo": "...", "assinatura": true}]}"""

PROMPT_ASSINATURAS = """Liste, de cima para baixo, cada linha de entrega desta ficha de EPI com a data
e o que está escrito na coluna "Assinatura" dessa linha. Se a célula estiver em branco, escreva "vazio".
Responda SOMENTE com JSON: {"linhas": [{"data": "DD/MM/AAAA", "assinatura": "..."}]}"""


def _imagem_b64(caminho: Path, lado_max: int = LADO_MAX) -> str:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")
    img.thumbnail((lado_max, lado_max))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def _perguntar(cliente: ClienteLLM, b64: str, texto: str, max_tokens: int) -> tuple[dict, float]:
    msg = [{"role": "user", "content": [
        {"type": "text", "text": texto},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}]
    resp = cliente.completar(msg, max_tokens=max_tokens)  # type: ignore[arg-type]
    return extrair_json(resp.texto), resp.custo_usd


def _campo(valor: Any) -> tuple[str | None, str]:
    """-> (valor, estado) com estado em ok | vazio | ilegivel."""
    if valor is None:
        return None, "ilegivel"
    s = str(valor).strip()
    n = s.lower()
    if n in ("", "vazio", "-", "null", "none"):
        return None, "vazio"
    if n in ("ilegivel", "ilegível", "?"):
        return None, "ilegivel"
    return s, "ok"


def _bool(valor: Any) -> bool | None:
    if isinstance(valor, bool):
        return valor
    s = str(valor).strip().lower()
    if s in ("true", "sim", "1", "assinado"):
        return True
    if s in ("false", "nao", "não", "0", "vazio"):
        return False
    return None


def _texto_assinado(valor: Any) -> bool | None:
    if valor is None:
        return None
    s = str(valor).strip().lower()
    if s in ("", "vazio", "-", "null", "none", "em branco", "branco"):
        return False
    if s in ("ilegivel", "ilegível", "?"):
        return None
    return True


def _pergunta_b(cliente: ClienteLLM, b64: str, linhas: list[LinhaDict]) -> tuple[list[str | None], float]:
    """Texto da coluna Assinatura de cada linha, alinhado à leitura A (por posição; por data se a contagem diferir)."""
    try:
        obj, custo = _perguntar(cliente, b64, PROMPT_ASSINATURAS, 800)
    except Exception:  # noqa: BLE001 — sem resposta B, a confiança cai
        return [None] * len(linhas), 0.0
    lista = [x for x in (obj.get("linhas") or []) if isinstance(x, dict)]
    if len(lista) == len(linhas):
        return [x.get("assinatura") for x in lista], custo
    por_data: dict[str | None, list[str | None]] = {}
    for x in lista:
        por_data.setdefault(normalizar_data(x.get("data")), []).append(x.get("assinatura"))
    return [(por_data.get(l.get("data")) or [None]).pop(0) for l in linhas], custo


_CAMINHOS: dict[str, Path] = {}  # origem (nome do arquivo) -> caminho completo, para reextrair


def caminho_da_origem(origem: str) -> Path | None:
    return _CAMINHOS.get(origem) or (Path(origem) if Path(origem).exists() else None)


def ler_foto(arquivo: str | Path) -> dict[str, Any]:
    """Lê a foto e devolve {"linhas": [LinhaDict], "cabecalho": {...}, "custo_usd": float, "modelo": str}."""
    caminho = Path(arquivo).resolve()
    _CAMINHOS[caminho.name] = caminho
    cliente = ClienteLLM(modelo=MODELO_VISAO, reserva=MODELO_VISAO_RESERVA, timeout_s=90, extra=False)
    b64 = _imagem_b64(caminho)

    bruto, custo = _perguntar(cliente, b64, PROMPT_LEITURA, 1500)
    cab = bruto.get("cabecalho") or {}
    nome, _ = _campo(cab.get("nome"))
    matricula, _ = _campo(cab.get("matricula"))
    funcao, _ = _campo(cab.get("funcao"))
    admissao_txt, _ = _campo(cab.get("data_admissao"))
    admissao = normalizar_data(admissao_txt) if admissao_txt else None
    funcionario_id = re.sub(r"\D", "", matricula or "") or (nome or caminho.stem)

    linhas: list[LinhaDict] = []
    n = 0
    for item in bruto.get("linhas") or []:
        if not isinstance(item, dict):
            continue
        # Linha fantasma: o modelo às vezes "lê" as linhas vazias da tabela. Sem data, EPI e CA não há entrega.
        if not any(_campo(item.get(c))[0] for c in ("data", "epi", "ca")):
            continue
        n += 1
        conf: dict[str, float] = {}
        data_txt, est = _campo(item.get("data"))
        data = normalizar_data(data_txt) if data_txt else None
        conf["data"] = 0.9 if data else (0.9 if est == "vazio" else 0.3)
        epi, est = _campo(item.get("epi"))
        conf["epi"] = 0.8 if epi else 0.3
        ca_txt, est = _campo(item.get("ca"))
        ca = normalizar_ca(ca_txt) if ca_txt else None
        ok_ca = bool(ca and 3 <= len(ca) <= 6)
        conf["ca"] = 0.9 if ok_ca else (0.9 if est == "vazio" else 0.3)
        if ca and not ok_ca:
            ca = None
        qtd_txt, _ = _campo(item.get("qtd"))
        m = re.search(r"\d+", qtd_txt or "")
        motivo, _ = _campo(item.get("motivo"))
        linhas.append({
            "funcionario_id": funcionario_id, "nome": nome or "", "funcao": (funcao or "").lower(),
            "linha": n, "data": data, "epi": epi or "", "qtd": int(m.group()) if m else 1, "ca": ca,
            "motivo": motivo, "assinatura": _bool(item.get("assinatura")), "confianca": conf,
            "origem": caminho.name,
            "data_admissao": admissao,  # campo interno (fora do contrato): coerência das datas
        })

    textos_b, custo_b = _pergunta_b(cliente, b64, linhas)
    custo += custo_b
    tipos = classificar_assinaturas(textos_b, nome)
    for l, texto_b, tipo in zip(linhas, textos_b, tipos):
        b = _texto_assinado(texto_b)
        a = l["assinatura"]
        if a is not None and a == b:
            conf_ass = CONF_CONCORDA
        elif a is None or b is None:
            l["assinatura"] = a if a is not None else b
            conf_ass = CONF_SO_UMA if l["assinatura"] is not None else 0.0
        else:
            l["assinatura"] = False  # na dúvida, a falta de assinatura é o que precisa ser conferido
            conf_ass = CONF_DISCORDA
        # O que está escrito confere com o nome do funcionário? ("entregue", "✓", "Marcos" na ficha do Fábio)
        if tipo in EFEITO_ASSINATURA:
            l["assinatura"], conf_ass = EFEITO_ASSINATURA[tipo]
        l["confianca"]["assinatura"] = conf_ass
        # rastro (campos internos, fora do contrato): o que cada pergunta respondeu e o que o código concluiu
        l["leitura_assinatura"] = {"a": a, "b": b}
        l["assinatura_texto"], l["assinatura_tipo"] = texto_b, tipo

    # CA que não combina com o EPI fica com baixa confiança. Testado e descartado: perguntar ao modelo
    # "é 14664 ou 17664?" (ele repete a própria leitura). A hipótese vem dos CAs da empresa, no grafo.
    conferir_ca(linhas)
    conferir_datas(linhas)  # entrega antes da admissão ou depois de hoje: data em dúvida, nunca trocada

    return {"linhas": linhas, "cabecalho": {"nome": nome, "matricula": matricula, "funcao": funcao,
                                            "data_admissao": admissao},
            "custo_usd": round(custo, 6), "modelo": MODELO_VISAO}


# Pergunta separada (não mexe nas perguntas das assinaturas, que foram medidas): só o cabeçalho.
PROMPT_TREINAMENTO = """Olhe só o CABEÇALHO desta ficha de entrega de EPI (acima da tabela de entregas).
Procure um campo cujo RÓTULO fale de treinamento (ex.: "Treinamento sobre uso do EPI (data)", "Treinamento:").
Em fichas impressas ele costuma ficar ao lado de "Data de admissão".

Olhe o que está escrito À MÃO dentro desse campo, e só dentro dele.
NUNCA use datas da tabela de entregas nem a data de admissão: se o campo de treinamento não tem nada
escrito à mão, ele está vazio, mesmo que a admissão ou a tabela tenham datas.

Responda SOMENTE com JSON:
{"tem_rotulo": true/false, "tem_escrita_a_mao": true/false, "data": "DD/MM/AAAA" ou null}
tem_rotulo: o cabeçalho tem um rótulo de treinamento?
tem_escrita_a_mao: há tinta de caneta DENTRO do espaço desse campo (não no rótulo impresso)?
data: só se tem_escrita_a_mao for true."""


def interpretar_treinamento(obj: dict[str, Any]) -> dict[str, Any]:
    """Resposta do modelo -> {"estado", "data"}: ok | vazio | sem_campo | ilegivel.

    Só "vazio" é lacuna: formulário sem o campo não prova que faltou treinamento.
    """
    if "tem_rotulo" in obj:  # formato sim/não
        if not _bool(obj.get("tem_rotulo")):
            return {"estado": "sem_campo", "data": None}
        if not _bool(obj.get("tem_escrita_a_mao")):
            return {"estado": "vazio", "data": None}
        obj = {"campo": "preenchido", "data": obj.get("data")}
    campo = re.sub(r"[\s_-]", "", str(obj.get("campo", "")).lower())
    if campo in ("semcampo", "naotem", "nãotem", "nao", "não"):
        return {"estado": "sem_campo", "data": None}
    if campo == "vazio":
        return {"estado": "vazio", "data": None}
    texto, estado = _campo(obj.get("data"))
    data = normalizar_data(texto) if texto else None
    if data:
        return {"estado": "ok", "data": data}
    return {"estado": "vazio" if estado == "vazio" else "ilegivel", "data": None}


def ler_treinamento(arquivo: str | Path) -> dict[str, Any]:
    """Lê o campo de treinamento do cabeçalho -> {"estado", "data", "custo_usd"} (~5-10 s)."""
    cliente = ClienteLLM(modelo=MODELO_VISAO, reserva=MODELO_VISAO_RESERVA, timeout_s=90, extra=False)
    obj, custo = _perguntar(cliente, _imagem_b64(Path(arquivo)), PROMPT_TREINAMENTO, 120)
    return {**interpretar_treinamento(obj or {}), "custo_usd": round(custo, 6)}


def reextrair_assinatura(arquivo: str | Path, linha: LinhaDict) -> dict[str, Any] | None:
    """Nova tentativa na assinatura: pergunta B de novo, com a foto em resolução maior."""
    cliente = ClienteLLM(modelo=MODELO_VISAO, reserva=MODELO_VISAO_RESERVA, timeout_s=90, extra=False)
    obj, _ = _perguntar(cliente, _imagem_b64(Path(arquivo), lado_max=2400), PROMPT_ASSINATURAS, 800)
    lista = [x for x in (obj.get("linhas") or []) if isinstance(x, dict)]
    mesmas = [x for x in lista if normalizar_data(x.get("data")) == linha.get("data")]
    i = int(linha.get("linha", 0)) - 1
    alvo = mesmas[0] if len(mesmas) == 1 else (lista[i] if 0 <= i < len(lista) else None)
    b = _texto_assinado(alvo.get("assinatura")) if alvo else None
    if b is None:
        return None
    # O rastro A/B some quando a linha passa pelo modelo Linha da API; aí vale a leitura atual como voto.
    rastro = linha.get("leitura_assinatura") or {"atual": linha.get("assinatura")}
    anteriores = [x for x in rastro.values() if x is not None]
    votos = anteriores + [b]
    maioria = max(set(votos), key=votos.count)
    unanime = votos.count(maioria) == len(votos)
    return {"valor": maioria, "confianca": CONF_CONCORDA if unanime else 0.7 if votos.count(maioria) >= 2 else CONF_DISCORDA}
