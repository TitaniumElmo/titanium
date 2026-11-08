"""Aviso por e-mail ao técnico ou ao RH quando uma pendência é criada ou reaberta.

Configuração no .env (Gmail: conta própria do Heitor + "senha de app"):
    SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_USER=...  SMTP_PASSWORD=...
    SMTP_FROM=Heitor <...>    HEITOR_EMAIL_TECNICO=...  HEITOR_EMAIL_RH=...
Sem SMTP_HOST ou sem o destinatário, só registra no log. O envio roda em outra
thread e nunca derruba o fluxo.

Segurança: o e-mail leva a ação da REGRA (texto fixo do código), não o texto
escrito pelo LLM. O LLM lê o conteúdo da planilha; uma célula com instruções
poderia fazê-lo escrever qualquer coisa (um link, por exemplo) num e-mail
enviado em nome do Heitor. O texto do LLM continua na pendência e na tela.

Nome do produto nos e-mails (remetente à parte, que vem de SMTP_FROM):
    HEITOR_NOME_NO_EMAIL=Elmo   (padrão: Elmo). Só o texto do e-mail muda.

Teste de envio (manda um e-mail para o técnico e para o RH configurados):
    python -m heitor.api.notificacao --teste
"""

from __future__ import annotations

import logging
import os
import smtplib
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterator, Optional

from heitor.contrato import Pendencia

log = logging.getLogger("heitor.notificacao")

_DESTINATARIO_ENV = {"tecnico": "HEITOR_EMAIL_TECNICO", "rh": "HEITOR_EMAIL_RH"}
_PARA_QUEM = {"tecnico": "técnico de segurança", "rh": "RH"}


def nome() -> str:
    """Nome do produto no texto dos e-mails."""
    return os.getenv("HEITOR_NOME_NO_EMAIL") or "Elmo"


def _texto(p: Pendencia, assunto: str, acao: str) -> str:
    return (
        f"{assunto}\n\n"
        f"Funcionário: {p.funcionario_id or '-'}\n"
        f"O que fazer: {acao}\n"
        f"Por quê: {p.motivo or '-'}\n"
        f"Prazo: {p.prazo.strftime('%d/%m/%Y')}\n\n"
        f"Pendência {p.id} (status: {p.status}), aberta pela auditoria {p.auditoria_id or '-'}.\n"
        f"O {nome()} aponta lacunas na prova documental das fichas de EPI; ele não afirma se há insalubridade.\n"
    )


# ---------------------------------------------------------------------------
# Lotes: uma auditoria (ou uma rodada de cobrança) manda UM e-mail por destinatário,
# com a lista das pendências. Um e-mail por pendência virava rajada no celular, e o
# Gmail bloqueia conta nova que manda dezenas de e-mails em poucos minutos.
# O lote é identificado por uma chave (o auditoria_id), não por contexto da thread:
# o agente cria as pendências de vários funcionários em threads diferentes.
# ---------------------------------------------------------------------------


@dataclass
class _Aviso:
    quem: str  # tecnico | rh | coordenador
    destinatario: Optional[str]
    tipo: str  # nova | reaberta | cobranca
    pendencia: Pendencia
    acao: str
    assunto: str  # assunto do e-mail individual
    texto: str  # corpo do e-mail individual


_lotes: dict[str, list[_Aviso]] = {}
_lotes_lock = threading.Lock()


@contextmanager
def agrupar(chave: Optional[str]) -> Iterator[None]:
    """Junta os avisos com esta chave e, na saída, manda um e-mail por destinatário."""
    if not chave:
        yield
        return
    with _lotes_lock:
        aninhado = chave in _lotes
        _lotes.setdefault(chave, [])
    try:
        yield
    finally:
        if not aninhado:
            with _lotes_lock:
                avisos = _lotes.pop(chave, [])
            _despachar(avisos)


def notificar(
    pendencia: Pendencia,
    reaberta: bool = False,
    acao_da_regra: Optional[str] = None,
    cobranca: int = 0,
    coordenador: bool = False,
    lote: Optional[str] = None,
) -> None:
    """acao_da_regra: a `acao_sugerida` do achado (texto das regras). Sem ela, vai uma ação genérica,
    nunca o texto do LLM. cobranca > 0: pendência em atraso; coordenador=True manda também ao
    HEITOR_EMAIL_COORDENADOR (sem ele, só registra). Dentro de um lote aberto (chave `lote`, ou o
    auditoria_id da pendência), o aviso espera o fim do lote para sair junto com os outros."""
    if cobranca:
        assunto = f"Cobrança {cobranca} do {nome()}: pendência em atraso"
    else:
        assunto = f"Pendência reaberta pelo {nome()}" if reaberta else f"Nova pendência do {nome()}"
    acao = acao_da_regra or f"ver a pendência no {nome()}"
    texto = _texto(pendencia, assunto, acao)
    assunto_completo = f"{assunto}: {acao[:70]}"
    tipo = "cobranca" if cobranca else "reaberta" if reaberta else "nova"
    alvos = [(pendencia.destino, os.getenv(_DESTINATARIO_ENV[pendencia.destino]))]
    if coordenador:
        alvos.append(("coordenador", os.getenv("HEITOR_EMAIL_COORDENADOR")))
    avisos = [_Aviso(quem, dest, tipo, pendencia, acao, assunto_completo, texto) for quem, dest in alvos]

    chave = lote or pendencia.auditoria_id
    with _lotes_lock:
        if chave and chave in _lotes:
            _lotes[chave].extend(avisos)
            return
    _despachar(avisos)


_PLURAL = {"nova": "novas", "reaberta": "reabertas", "cobranca": "em atraso"}
_ROTULO = {"nova": "nova", "reaberta": "reaberta", "cobranca": "em atraso"}


def _despachar(avisos: list[_Aviso]) -> None:
    """Um e-mail por destinatário: o aviso sozinho no formato normal; vários, numa lista."""
    por_destinatario: dict[tuple[str, Optional[str]], list[_Aviso]] = {}
    for a in avisos:
        por_destinatario.setdefault((a.quem, a.destinatario), []).append(a)
    for (quem, destinatario), grupo in por_destinatario.items():
        if len(grupo) == 1:
            assunto, texto = grupo[0].assunto, grupo[0].texto
        else:
            assunto, texto = _resumo_do_lote(grupo)
        if not os.getenv("SMTP_HOST") or not destinatario:
            log.info("[aviso para %s, sem e-mail configurado]\n%s", quem, texto)
            continue
        _disparar(destinatario, assunto, texto)


def _disparar(destinatario: str, assunto: str, texto: str) -> None:
    """Envia em segundo plano: o SMTP nunca segura a auditoria."""
    threading.Thread(target=_enviar, args=(destinatario, assunto, texto), daemon=True).start()


def _resumo_do_lote(grupo: list[_Aviso]) -> tuple[str, str]:
    """Vários avisos para a mesma pessoa: um e-mail com a lista, prazo mais curto primeiro."""
    tipos = {a.tipo for a in grupo}
    misturado = len(tipos) > 1
    qual = "para você" if misturado else _PLURAL[next(iter(tipos))]
    assunto = f"{nome()}: {len(grupo)} pendências {qual}"
    linhas = [f"{assunto}\n"]
    for i, a in enumerate(sorted(grupo, key=lambda x: (x.pendencia.prazo, x.pendencia.funcionario_id or "")), 1):
        p = a.pendencia
        quem = p.funcionario_nome or p.funcionario_id or "-"
        rotulo = f" [{_ROTULO[a.tipo]}]" if misturado else ""
        alta = " (prioridade alta)" if p.prioridade == "alta" else ""
        linhas.append(
            f"{i}. {quem}{rotulo}\n"
            f"   O que fazer: {a.acao}\n"
            f"   Por quê: {p.motivo or '-'}\n"
            f"   Prazo: {p.prazo.strftime('%d/%m/%Y')}{alta}\n"
        )
    linhas.append(f"O {nome()} aponta lacunas na prova documental das fichas de EPI; ele não afirma se há insalubridade.\n")
    return assunto, "\n".join(linhas)


def _enviar(destinatario: str, assunto: str, texto: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", "heitor@localhost")
    msg["To"] = destinatario
    msg.set_content(texto)
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        log.info("e-mail enviado para %s: %s", destinatario, assunto)
        return True
    except Exception as exc:
        log.error("falha ao enviar e-mail para %s (%s: %s); o fluxo segue", destinatario, type(exc).__name__, exc)
        return False


def _teste() -> int:
    """Manda um e-mail de teste para cada destinatário configurado. Não imprime a senha."""
    from dotenv import load_dotenv

    load_dotenv()
    faltam = [v for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD") if not os.getenv(v)]
    if faltam:
        print(f"faltam no .env: {', '.join(faltam)}")
        return 1
    ok = True
    for destino, var in _DESTINATARIO_ENV.items():
        para = os.getenv(var)
        if not para:
            print(f"{var} vazio: sem e-mail para o {_PARA_QUEM[destino]}")
            continue
        enviado = _enviar(para, f"Teste do {nome()}", f"Teste de envio do {nome()} para o {_PARA_QUEM[destino]}.\n"
                                                    "Se chegou, os avisos de pendência vão chegar aqui.\n")
        print(f"{'enviado' if enviado else 'FALHOU'}: {_PARA_QUEM[destino]} ({para})")
        ok &= enviado
    return 0 if ok else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(message)s")
    sys.exit(_teste() if "--teste" in sys.argv else 0)
