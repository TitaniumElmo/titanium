"""Aviso ao técnico/RH sobre pendências.

O canal (e-mail ou Telegram) ainda está em aberto (CLAUDE.md, seção 12).
Por enquanto: e-mail por SMTP se as variáveis estiverem configuradas; se não,
só registra no log. O envio roda em outra thread e nunca derruba o fluxo.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
from email.message import EmailMessage

from heitor.contrato import Pendencia

log = logging.getLogger("heitor.notificacao")

_DESTINATARIO_ENV = {"tecnico": "HEITOR_EMAIL_TECNICO", "rh": "HEITOR_EMAIL_RH"}


def _texto(p: Pendencia, assunto: str) -> str:
    return (
        f"{assunto}\n\n"
        f"Pendência: {p.id} (status: {p.status})\n"
        f"Funcionário: {p.funcionario_id or '-'}\n"
        f"Ação: {p.acao}\n"
        f"Motivo: {p.motivo or '-'}\n"
        f"Prazo: {p.prazo.isoformat()}\n"
    )


def notificar(pendencia: Pendencia, assunto: str = "Nova pendência do Heitor") -> None:
    destinatario = os.getenv(_DESTINATARIO_ENV[pendencia.destino])
    texto = _texto(pendencia, assunto)
    if not os.getenv("SMTP_HOST") or not destinatario:
        log.info("[aviso para %s, sem e-mail configurado]\n%s", pendencia.destino, texto)
        return
    threading.Thread(target=_enviar, args=(destinatario, assunto, texto), daemon=True).start()


def _enviar(destinatario: str, assunto: str, texto: str) -> None:
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
    except Exception:
        log.exception("falha ao enviar e-mail para %s; o fluxo segue", destinatario)
