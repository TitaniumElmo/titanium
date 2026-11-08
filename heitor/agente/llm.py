"""Cliente do LLM (Featherless, API compatível com OpenAI).

Configuração pelo .env:
    FEATHERLESS_API_KEY   chave (obrigatória para usar o LLM)
    HEITOR_MODELO         modelo principal (padrão: Mistral Small 3.2)
    HEITOR_MODELO_RESERVA modelo usado se o principal falhar duas vezes
    HEITOR_LLM=off        desliga o LLM (testes e demo offline): o agente usa
                          a política determinística de grafo.py
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Sem override: o que já está definido vence o .env. Com override=True, o .env atropelava as
# variáveis que os testes esvaziam de propósito (SMTP_HOST, destinatários, Drive), e rodar o
# pytest numa máquina com e-mail configurado mandava e-mails de verdade. Também no deploy, a
# configuração da plataforma tem de vencer um .env esquecido. Variável velha exportada no
# shell: `unset NOME` antes de rodar.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = "https://api.featherless.ai/v1"
MODELO_PADRAO = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
MODELO_RESERVA_PADRAO = "Qwen/Qwen3-30B-A3B-Instruct-2507"
TEMPERATURA = 0.0  # demo previsível
TIMEOUT_S = 15  # por tentativa; a demo não pode ficar parada esperando o provedor


class LLMIndisponivel(RuntimeError):
    """O LLM falhou (com nova tentativa e reserva). O grafo segue sem ele."""


@dataclass
class RespostaLLM:
    texto: str
    custo_usd: float
    tokens_entrada: int
    tokens_saida: int
    modelo: str
    latencia_s: float


def llm_ligado() -> bool:
    return os.getenv("HEITOR_LLM", "on").lower() not in ("off", "0", "false", "nao", "não")


@dataclass
class Provedor:
    nome: str
    base_url: str
    chave: str
    modelo: str


def _provedores(modelo: str | None, reserva: str | None, extra: bool) -> list[Provedor]:
    """Ordem de tentativa: Featherless (principal), Featherless (reserva) e, se configurado, um provedor extra.

    Provedor extra no .env (qualquer API compatível com OpenAI; ex.: Groq):
        HEITOR_LLM_EXTRA_URL=https://api.groq.com/openai/v1
        HEITOR_LLM_EXTRA_CHAVE=...
        HEITOR_LLM_EXTRA_MODELO=llama-3.3-70b-versatile
    """
    lista = []
    chave = os.getenv("FEATHERLESS_API_KEY")
    if chave:
        lista.append(Provedor("featherless", BASE_URL, chave, modelo or os.getenv("HEITOR_MODELO", MODELO_PADRAO)))
        lista.append(Provedor("featherless-reserva", BASE_URL, chave,
                              reserva or os.getenv("HEITOR_MODELO_RESERVA", MODELO_RESERVA_PADRAO)))
    if extra and os.getenv("HEITOR_LLM_EXTRA_URL") and os.getenv("HEITOR_LLM_EXTRA_CHAVE"):
        lista.append(Provedor("extra", os.environ["HEITOR_LLM_EXTRA_URL"], os.environ["HEITOR_LLM_EXTRA_CHAVE"],
                              os.getenv("HEITOR_LLM_EXTRA_MODELO", "llama-3.3-70b-versatile")))
    return lista


class ClienteLLM:
    def __init__(self, modelo: str | None = None, reserva: str | None = None, timeout_s: float | None = None,
                 extra: bool = True):
        """timeout_s: por tentativa. Texto usa o curto (demo não pode travar); visão passa um maior.
        extra=False: só Featherless (a leitura de foto precisa de um modelo de visão)."""
        from openai import OpenAI  # import tardio: testes offline não precisam

        self.provedores = _provedores(modelo, reserva, extra)
        if not self.provedores:
            raise LLMIndisponivel("nenhum provedor de LLM configurado no .env")
        timeout = timeout_s if timeout_s is not None else float(os.getenv("HEITOR_LLM_TIMEOUT", TIMEOUT_S))
        self._clientes = {p.nome: OpenAI(base_url=p.base_url, api_key=p.chave, timeout=timeout, max_retries=0)
                          for p in self.provedores}
        self.modelos = [p.modelo for p in self.provedores]

    def completar(self, mensagens: list[dict[str, str]], max_tokens: int = 400) -> RespostaLLM:
        """Uma tentativa por provedor, em ordem. Todos falharam -> LLMIndisponivel (o grafo segue sem LLM)."""
        erros = []
        for p in self.provedores:
            inicio = time.monotonic()
            try:
                r = self._clientes[p.nome].chat.completions.create(
                    model=p.modelo, messages=mensagens, temperature=TEMPERATURA, max_tokens=max_tokens,
                )
                if not r.choices or not r.choices[0].message.content:
                    raise LLMIndisponivel(f"resposta vazia de {p.modelo}")
                u = r.usage
                extra = (u.model_extra or {}) if u else {}
                return RespostaLLM(
                    texto=r.choices[0].message.content,
                    custo_usd=float(extra.get("cost") or 0.0),
                    tokens_entrada=u.prompt_tokens if u else 0,
                    tokens_saida=u.completion_tokens if u else 0,
                    modelo=f"{p.nome}:{p.modelo}",
                    latencia_s=time.monotonic() - inicio,
                )
            except Exception as e:  # rede, timeout, 5xx, resposta vazia...
                erros.append(f"{p.nome}: {type(e).__name__} {str(e)[:80]}")
        raise LLMIndisponivel(" | ".join(erros)[:400])


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def extrair_json(texto: str) -> dict[str, Any]:
    """Lê o primeiro objeto JSON da resposta (tolera ```json e texto em volta)."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(texto)
    except json.JSONDecodeError:
        m = _JSON_OBJ.search(texto)
        if not m:
            raise ValueError("resposta sem JSON")
        bruto = m.group(0)
        # Corta no último '}' que fecha um objeto válido.
        for fim in range(len(bruto), 0, -1):
            if bruto[fim - 1] != "}":
                continue
            try:
                obj = json.loads(bruto[:fim])
                break
            except json.JSONDecodeError:
                continue
        else:
            raise ValueError("JSON inválido na resposta")
    if not isinstance(obj, dict):
        raise ValueError("a resposta não é um objeto JSON")
    return obj
