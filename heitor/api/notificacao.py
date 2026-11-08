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

Teste de envio (manda um e-mail para o técnico e para o RH configurados):
    python -m heitor.api.notificacao --teste
"""

from __future__ import annotations

import logging
import os
import smtplib
import sys
import threading
from email.message import EmailMessage
from typing import Optional

from heitor.contrato import Pendencia

log = logging.getLogger("heitor.notificacao")

_DESTINATARIO_ENV = {"tecnico": "HEITOR_EMAIL_TECNICO", "rh": "HEITOR_EMAIL_RH"}
_PARA_QUEM = {"tecnico": "técnico de segurança", "rh": "RH"}


def _texto(p: Pendencia, assunto: str, acao: str) -> str:
    return (
        f"{assunto}\n\n"
        f"Funcionário: {p.funcionario_id or '-'}\n"
        f"O que fazer: {acao}\n"
        f"Por quê: {p.motivo or '-'}\n"
        f"Prazo: {p.prazo.strftime('%d/%m/%Y')}\n\n"
        f"Pendência {p.id} (status: {p.status}), aberta pela auditoria {p.auditoria_id or '-'}.\n"
        "O Heitor aponta lacunas na prova documental das fichas de EPI; ele não afirma se há insalubridade.\n"
    )


def notificar(
    pendencia: Pendencia, assunto: str = "Nova pendência do Heitor", acao_da_regra: Optional[str] = None
) -> None:
    """acao_da_regra: a `acao_sugerida` do achado (texto das regras). Sem ela, vai uma ação genérica,
    nunca o texto do LLM."""
    destinatario = os.getenv(_DESTINATARIO_ENV[pendencia.destino])
    acao = acao_da_regra or "ver a pendência no Heitor"
    texto = _texto(pendencia, assunto, acao)
    assunto_completo = f"{assunto}: {acao[:70]}"
    if not os.getenv("SMTP_HOST") or not destinatario:
        log.info("[aviso para %s, sem e-mail configurado]\n%s", pendencia.destino, texto)
        return
    threading.Thread(target=_enviar, args=(destinatario, assunto_completo, texto), daemon=True).start()


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
        enviado = _enviar(para, "Teste do Heitor", f"Teste de envio do Heitor para o {_PARA_QUEM[destino]}.\n"
                                                    "Se chegou, os avisos de pendência vão chegar aqui.\n")
        print(f"{'enviado' if enviado else 'FALHOU'}: {_PARA_QUEM[destino]} ({para})")
        ok &= enviado
    return 0 if ok else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(message)s")
    sys.exit(_teste() if "--teste" in sys.argv else 0)
