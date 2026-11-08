"""Confere a ficha de papel contra a planilha: a foto só precisa provar a ASSINATURA.

Data, EPI, CA e quantidade vêm da planilha de controle (digitados, confiáveis). Da foto, o que
importa é o que só o papel tem: a assinatura do trabalhador em cada entrega.

  A) pergunta guiada: a IA recebe as entregas da planilha e, para cada uma, acha a linha na
     ficha e transcreve a assinatura (ou diz que a entrega não está no papel);
  B) pergunta independente: a IA lista a coluna Assinatura SEM ver a planilha (contraprova:
     com a lista na mão, o modelo tende a "confirmar" o que leu nela).
Concordaram -> confiança alta. Discordaram -> dúvida, que vira conferência no papel.
A assinatura transcrita é comparada com o nome DIGITADO na planilha (assinatura.py).

Achados novos possíveis:
  - entrega na planilha sem linha na ficha  -> falta a prova da entrega
  - linha na ficha sem entrega na planilha  -> controle desatualizado
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from heitor.agente.assinatura import EFEITO as EFEITO_ASSINATURA
from heitor.agente.assinatura import classificar_linhas
from heitor.agente.ferramentas import normalizar_data
from heitor.agente.foto import (CONF_CONCORDA, CONF_DISCORDA, CONF_SO_UMA, MODELO_VISAO, MODELO_VISAO_RESERVA,
                                PROMPT_ASSINATURAS, _imagem_b64, _perguntar, _texto_assinado)
from heitor.agente.foto import ler_treinamento  # noqa: F401  (a ferramenta chama CAS.ler_treinamento; os testes trocam)
from heitor.agente.llm import ClienteLLM

log = logging.getLogger(__name__)

PROMPT_GUIADO = """Esta é a foto da ficha de entrega de EPI de {nome}.
Segundo a planilha de controle da empresa, estas entregas foram feitas:
{lista}

Para CADA entrega da lista, encontre na tabela da foto a linha correspondente (mesma data e mesmo EPI)
e transcreva EXATAMENTE o que está escrito na coluna "Assinatura do funcionário" DESSA linha.
- Se a célula de assinatura estiver em branco, escreva "vazio".
- Se a entrega NÃO aparece na ficha, use "encontrada": false.
- Cuidado: uma assinatura pode invadir a linha de cima ou de baixo; transcreva só o que está na linha certa.
Depois, liste as linhas da ficha que NÃO estão na lista (ignore linhas riscadas).

Responda SOMENTE com JSON:
{{"entregas": [{{"id": 1, "encontrada": true, "assinatura": "..."}}],
  "linhas_fora_da_lista": [{{"data": "DD/MM/AAAA", "epi": "..."}}]}}"""


def _br(data_iso: str | None) -> str:
    if not data_iso:
        return "data não informada"
    a, m, d = str(data_iso)[:10].split("-")
    return f"{d}/{m}/{a}"


def _dict(x: Any) -> dict[str, Any]:
    return x.model_dump(mode="json") if hasattr(x, "model_dump") else dict(x)


# Veto: um modelo de visão DIFERENTE lê a coluna de assinatura. A e B usam o mesmo modelo e às vezes erram juntos
# ("completa o padrão": linha em branco entre linhas assinadas). O veto só tira uma assinatura (vira conferência
# humana), nunca aceita uma. Medido em 08/11; desliga com HEITOR_VETO_ASSINATURA=off.
MODELO_VETO = os.getenv("HEITOR_MODELO_VETO", "Qwen/Qwen3-VL-32B-Instruct")


def veto_ligado() -> bool:
    return os.getenv("HEITOR_VETO_ASSINATURA", "on").lower() not in ("off", "0", "false", "nao", "não")


def _ler_veto(b64: str) -> tuple[list[dict[str, Any]], float]:
    cliente = ClienteLLM(modelo=MODELO_VETO, reserva=MODELO_VETO, timeout_s=90, extra=False)
    obj, custo = _perguntar(cliente, b64, PROMPT_ASSINATURAS, 800)
    return [x for x in obj.get("linhas") or [] if isinstance(x, dict)], custo


def aplicar_veto(linhas: list[dict[str, Any]], textos_veto: list[str | None]) -> list[int]:
    """Linha aceita como assinada que o outro modelo lê em branco vira dúvida. Devolve as linhas vetadas."""
    vetadas = []
    for l, texto in zip(linhas, textos_veto):
        if l.get("assinatura") is True and _texto_assinado(texto) is False:
            l["assinatura"] = False  # como na discordância entre A e B: a falta é o que se confere
            l.setdefault("confianca", {})["assinatura"] = CONF_DISCORDA
            l.setdefault("leitura_assinatura", {})["veto"] = texto
            vetadas.append(l.get("linha"))
    return vetadas


def _dia_mes(data_iso: str | None) -> str | None:
    return str(data_iso)[5:10] if data_iso else None


def _alinhar_b(linhas: list[dict[str, Any]], lista_b: list[dict[str, Any]]) -> list[str | None]:
    """Texto da coluna Assinatura (pergunta B) para cada entrega da planilha.

    A pergunta B lê o papel sem a lista e erra datas (o "5" que vira "3"). Por isso:
    1) mesma quantidade de linhas -> casa pela POSIÇÃO (papel e planilha seguem a mesma ordem);
    2) senão, data exata; 3) senão, mesmo dia e mês (ignorando o ano), se só houver um candidato.
    """
    # linhas vazias da tabela que o modelo listou não contam
    lista_b = [x for x in lista_b if x.get("data") or _texto_assinado(x.get("assinatura")) is not False]
    if len(lista_b) == len(linhas):
        return [x.get("assinatura") for x in lista_b]
    livres = [(normalizar_data(x.get("data")), x.get("assinatura")) for x in lista_b]
    textos: list[str | None] = []
    for l in linhas:
        d = str(l.get("data"))[:10] if l.get("data") else None
        achou = next((i for i, (db, _) in enumerate(livres) if d and db == d), None)
        if achou is None:
            mesmos = [i for i, (db, _) in enumerate(livres) if d and _dia_mes(db) == _dia_mes(d)]
            achou = mesmos[0] if mesmos else None  # várias entregas no mesmo dia: segue a ordem do papel
        textos.append(livres.pop(achou)[1] if achou is not None else None)
    return textos


def _aparece_em(linha: dict[str, Any], lista: list[dict[str, Any]]) -> bool:
    """A entrega da planilha aparece na lista lida do papel? Mesmo dia e mês (o ano é o que mais se lê errado)
    e mesmo tipo de EPI."""
    from heitor.agente.conferencia_ca import familia

    dm, fam = _dia_mes(linha.get("data")), familia(linha.get("epi"))
    return any(_dia_mes(normalizar_data(x.get("data"))) == dm and (fam is None or familia(x.get("epi")) == fam)
               for x in lista)


def conferir_assinaturas(arquivo: str | Path, linhas_planilha: list[Any]) -> dict[str, Any]:
    """Confere a foto da ficha de UM funcionário contra as entregas dele na planilha.

    Devolve {"linhas": [...], "fora_da_planilha": [...], "custo_usd": float}. Cada linha é a da planilha
    (sem nada alterado nos dados digitados), com assinatura, confianca["assinatura"] e os campos internos
    na_ficha, assinatura_texto, assinatura_tipo e leitura_assinatura.
    """
    linhas = [_dict(l) for l in linhas_planilha]
    if not linhas:
        return {"linhas": [], "fora_da_planilha": [], "custo_usd": 0.0}
    nome = next((l.get("nome") for l in linhas if l.get("nome")), "") or ""
    cliente = ClienteLLM(modelo=MODELO_VISAO, reserva=MODELO_VISAO_RESERVA, timeout_s=90, extra=False)
    b64 = _imagem_b64(Path(arquivo))

    lista = "\n".join(f"{i}. {_br(l.get('data'))} - {l.get('epi')} - qtd {l.get('qtd', 1)}"
                      + (f" - CA {l['ca']}" if l.get("ca") else "") for i, l in enumerate(linhas, start=1))
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=1)
    futuro_veto = pool.submit(_ler_veto, b64) if veto_ligado() else None
    try:
        obj_a, custo = _perguntar(cliente, b64, PROMPT_GUIADO.format(nome=nome or "funcionário", lista=lista), 1200)
    except Exception:  # noqa: BLE001 — sem a pergunta guiada, tudo fica em dúvida
        obj_a, custo = {}, 0.0
    respostas = {int(r["id"]): r for r in obj_a.get("entregas") or []
                 if isinstance(r, dict) and str(r.get("id", "")).isdigit()}
    try:
        obj_b, custo_b = _perguntar(cliente, b64, PROMPT_ASSINATURAS, 800)
        custo += custo_b
    except Exception:  # noqa: BLE001
        obj_b = {}
    textos_b = _alinhar_b(linhas, [x for x in obj_b.get("linhas") or [] if isinstance(x, dict)])

    fora_a = [x for x in obj_a.get("linhas_fora_da_lista") or [] if isinstance(x, dict)]
    textos_a = []
    for i, l in enumerate(linhas, start=1):
        r = respostas.get(i) or {}
        encontrada = r.get("encontrada")
        l["na_ficha"] = None if encontrada is None else bool(encontrada) and str(encontrada).lower() != "false"
        if l["na_ficha"] is False and _aparece_em(l, fora_a):
            # Contradição da própria resposta: "não encontrei" a entrega, mas listou a mesma entrega como
            # linha "fora da lista". A linha existe; vira dúvida (conferência), nunca "falta a prova".
            l["na_ficha"] = None
        texto = r.get("assinatura")
        if texto is not None and "encontrad" in str(texto).lower():  # o modelo às vezes escreve isso no campo
            texto = None
        textos_a.append(texto if l["na_ficha"] is not False else None)

    tipos = classificar_linhas(textos_a, nome)
    for l, texto_a, texto_b, tipo in zip(linhas, textos_a, textos_b, tipos):
        conf = dict(l.get("confianca") or {})
        if l["na_ficha"] is False:
            # A diz que a entrega não está no papel; B confirma se nenhuma linha da ficha tem essa data.
            l["assinatura"] = None
            conf["assinatura"] = CONF_CONCORDA if texto_b is None else CONF_DISCORDA
            l["assinatura_tipo"] = "sem_linha_na_ficha"
        else:
            a, b = _texto_assinado(texto_a), _texto_assinado(texto_b)
            if a is not None and a == b:
                l["assinatura"], c = a, CONF_CONCORDA
            elif a is None or b is None:
                l["assinatura"] = a if a is not None else b
                c = CONF_SO_UMA if l["assinatura"] is not None else 0.0
            else:
                l["assinatura"], c = False, CONF_DISCORDA  # na dúvida, a falta de assinatura é o que se confere
            if tipo in EFEITO_ASSINATURA:
                l["assinatura"], c = EFEITO_ASSINATURA[tipo]
            conf["assinatura"] = c
            l["assinatura_tipo"] = tipo
        l["confianca"] = conf
        l["assinatura_texto"] = texto_a
        l["leitura_assinatura"] = {"a": texto_a, "b": texto_b}

    vetadas: list[int] = []
    if futuro_veto is not None:
        try:
            lista_veto, custo_veto = futuro_veto.result()
            custo += custo_veto
            vetadas = aplicar_veto(linhas, _alinhar_b(linhas, lista_veto))
        except Exception as e:  # noqa: BLE001 — o veto é extra: sem ele, fica como antes
            log.warning("veto de assinatura falhou: %r", e)
    pool.shutdown(wait=False)

    # Linha do papel fora da planilha: depende da leitura aberta (datas frágeis). Só serve para conferência.
    fora = [{"data": normalizar_data(x.get("data")), "epi": x.get("epi")} for x in fora_a
            if not any(_aparece_em(l, [x]) for l in linhas)]
    return {"linhas": linhas, "fora_da_planilha": fora, "custo_usd": round(custo, 6), "vetadas": vetadas}
