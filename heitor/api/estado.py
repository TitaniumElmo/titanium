"""Estado da aplicação, em memória.

As rotas e as ferramentas só falam com a classe `Estado`, nunca com os
dicionários. Para trocar por SQLite/Postgres, basta reescrever esta classe
com os mesmos métodos.

Tudo que entra e sai é copiado, para uma thread não alterar o objeto de outra
(e para o comportamento ser o mesmo de um banco de verdade).
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Callable, Optional

from heitor.api.modelos import Auditoria
from heitor.contrato import Achado, Evento, Linha, Pendencia

log = logging.getLogger("heitor.estado")


class Estado:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Os contadores não zeram no reset: uma thread antiga que termine
        # depois do reset nunca gera um id repetido.
        self._contadores: dict[str, itertools.count] = defaultdict(lambda: itertools.count(1))
        self._removidas: set[str] = set()  # auditorias apagadas pelo reset
        self.limpar()

    def limpar(self) -> None:
        with self._lock:
            # Cada limpeza (reset da demo, troca de pasta) começa uma geração nova do log. O feed SSE
            # manda a geração no id do evento: quem reconecta com um id da geração antiga lê do zero
            # em vez de esperar o log novo passar da posição antiga (o feed ficaria mudo).
            self._geracao = getattr(self, "_geracao", 0) + 1
            self._removidas |= set(getattr(self, "_auditorias", {}))
            self._auditorias: dict[str, Auditoria] = {}
            self._linhas: dict[str, list[Linha]] = {}
            self._achados: dict[str, dict[str, Achado]] = defaultdict(dict)  # auditoria -> id -> achado
            self._pendencias: dict[str, Pendencia] = {}
            self._eventos: dict[str, list[Evento]] = defaultdict(list)
            self._log: list[Evento] = []  # todos os eventos, na ordem em que chegaram

    def novo_id(self, prefixo: str) -> str:
        with self._lock:
            return f"{prefixo}-{next(self._contadores[prefixo])}"

    def _aceita(self, auditoria_id: Optional[str], o_que: str) -> bool:
        """Descarta gravações de auditorias apagadas pelo reset (thread antiga
        terminando depois). Auditoria desconhecida é aceita: o agente também roda
        fora da API (testes e linha de comando da Sofia)."""
        if auditoria_id in self._removidas:
            log.warning("%s ignorado: auditoria %s foi apagada pelo reset", o_que, auditoria_id)
            return False
        return True

    # -- auditorias ---------------------------------------------------------

    def criar_auditoria(
        self,
        auditoria_id: str,
        arquivos: list[str],
        disparado_por: Optional[str] = None,
        descricao_disparo: Optional[str] = None,
    ) -> Auditoria:
        aud = Auditoria(
            id=auditoria_id, criada_em=datetime.now(), arquivos=arquivos,
            disparado_por=disparado_por, descricao_disparo=descricao_disparo,
        )
        with self._lock:
            self._auditorias[aud.id] = aud
            self._linhas[aud.id] = []
            self._achados[aud.id] = {}
            self._eventos[aud.id] = []
        return aud.model_copy(deep=True)

    def obter_auditoria(self, auditoria_id: str) -> Optional[Auditoria]:
        with self._lock:
            aud = self._auditorias.get(auditoria_id)
            return aud.model_copy(deep=True) if aud else None

    def listar_auditorias(self) -> list[Auditoria]:
        """Mais recente primeiro."""
        with self._lock:
            return [a.model_copy(deep=True) for a in sorted(self._auditorias.values(), key=lambda a: a.criada_em, reverse=True)]

    def atualizar_auditoria(self, auditoria_id: str, **campos) -> None:
        with self._lock:
            if auditoria_id in self._auditorias:
                aud = self._auditorias[auditoria_id]
                self._auditorias[auditoria_id] = aud.model_copy(update=campos)

    # -- linhas -------------------------------------------------------------

    def salvar_linhas(self, auditoria_id: str, linhas: list[Linha]) -> None:
        with self._lock:
            if self._aceita(auditoria_id, "linhas"):
                self._linhas[auditoria_id] = [l.model_copy(deep=True) for l in linhas]

    def obter_linhas(self, auditoria_id: str) -> list[Linha]:
        with self._lock:
            return [l.model_copy(deep=True) for l in self._linhas.get(auditoria_id, [])]

    # -- achados ------------------------------------------------------------

    def salvar_achado(self, achado: Achado) -> None:
        with self._lock:
            if self._aceita(achado.auditoria_id, f"achado {achado.id}"):
                self._achados[achado.auditoria_id][achado.id] = achado.model_copy(deep=True)

    def listar_achados(self, auditoria_id: str) -> list[Achado]:
        with self._lock:
            return [a.model_copy(deep=True) for a in self._achados.get(auditoria_id, {}).values()]

    def obter_achado(self, achado_id: str, auditoria_id: Optional[str] = None) -> Optional[Achado]:
        with self._lock:
            grupos = [self._achados.get(auditoria_id, {})] if auditoria_id else list(self._achados.values())
            for grupo in grupos:
                if achado_id in grupo:
                    return grupo[achado_id].model_copy(deep=True)
            return None

    # -- pendências ---------------------------------------------------------

    def salvar_pendencia(self, pendencia: Pendencia) -> None:
        with self._lock:
            if self._aceita(pendencia.auditoria_id, f"pendência {pendencia.id}"):
                self._pendencias[pendencia.id] = pendencia.model_copy(deep=True)

    def obter_pendencia(self, pendencia_id: str) -> Optional[Pendencia]:
        with self._lock:
            p = self._pendencias.get(pendencia_id)
            return p.model_copy(deep=True) if p else None

    def atualizar_pendencia(self, pendencia_id: str, alterar: Callable[[Pendencia], None]) -> Pendencia:
        """Aplica `alterar` na pendência de forma atômica. KeyError se não existir."""
        with self._lock:
            p = self._pendencias[pendencia_id].model_copy(deep=True)
            alterar(p)  # pode lançar exceção: nesse caso nada é gravado
            self._pendencias[pendencia_id] = p
            return p.model_copy(deep=True)

    def listar_pendencias(self, **filtros: Optional[str]) -> list[Pendencia]:
        """Filtros aceitos: auditoria_id, destino, status, funcionario_id, achado_id."""
        ativos = {k: v for k, v in filtros.items() if v is not None}
        with self._lock:
            return [
                p.model_copy(deep=True)
                for p in self._pendencias.values()
                if all(getattr(p, k) == v for k, v in ativos.items())
            ]

    # -- eventos ------------------------------------------------------------

    def registrar_evento(self, evento: Evento) -> None:
        with self._lock:
            if self._aceita(evento.auditoria_id, "evento"):
                self._eventos[evento.auditoria_id].append(evento.model_copy(deep=True))
                self._log.append(evento.model_copy(deep=True))

    def geracao(self) -> int:
        with self._lock:
            return self._geracao

    def log_desde(self, inicio: int = 0) -> list[Evento]:
        """Todos os eventos de todas as auditorias, na ordem em que chegaram."""
        with self._lock:
            return [e.model_copy(deep=True) for e in self._log[inicio:]]

    def eventos_desde(self, auditoria_id: str, inicio: int = 0) -> list[Evento]:
        with self._lock:
            return [e.model_copy(deep=True) for e in self._eventos.get(auditoria_id, [])[inicio:]]


estado = Estado()
