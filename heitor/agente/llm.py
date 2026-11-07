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

# override=True: o .env do projeto vence variáveis antigas exportadas no shell.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

BASE_URL = "https://api.featherless.ai/v1"
MODELO_PADRAO = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
MODELO_RESERVA_PADRAO = "Qwen/Qwen3-30B-A3B-Instruct-2507"
TEMPERATURA = 0.0  # demo previsível
TIMEOUT_S = 60


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


class ClienteLLM:
    def __init__(self, modelo: str | None = None, reserva: str | None = None):
        from openai import OpenAI  # import tardio: testes offline não precisam

        chave = os.getenv("FEATHERLESS_API_KEY")
        if not chave:
            raise LLMIndisponivel("FEATHERLESS_API_KEY ausente no .env")
        self._cliente = OpenAI(base_url=BASE_URL, api_key=chave, timeout=TIMEOUT_S, max_retries=0)
        self.modelos = [modelo or os.getenv("HEITOR_MODELO", MODELO_PADRAO),
                        reserva or os.getenv("HEITOR_MODELO_RESERVA", MODELO_RESERVA_PADRAO)]

    def completar(self, mensagens: list[dict[str, str]], max_tokens: int = 400) -> RespostaLLM:
        """Tenta o modelo principal duas vezes e depois o reserva uma vez."""
        tentativas = [self.modelos[0], self.modelos[0], self.modelos[1]]
        ultimo_erro: Exception | None = None
        for modelo in tentativas:
            inicio = time.monotonic()
            try:
                r = self._cliente.chat.completions.create(
                    model=modelo, messages=mensagens, temperature=TEMPERATURA, max_tokens=max_tokens,
                )
                if not r.choices or not r.choices[0].message.content:
                    raise LLMIndisponivel(f"resposta vazia de {modelo}")
                u = r.usage
                extra = (u.model_extra or {}) if u else {}
                return RespostaLLM(
                    texto=r.choices[0].message.content,
                    custo_usd=float(extra.get("cost") or 0.0),
                    tokens_entrada=u.prompt_tokens if u else 0,
                    tokens_saida=u.completion_tokens if u else 0,
                    modelo=modelo,
                    latencia_s=time.monotonic() - inicio,
                )
            except Exception as e:  # rede, 5xx, resposta vazia...
                ultimo_erro = e
        raise LLMIndisponivel(str(ultimo_erro)[:300])


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
