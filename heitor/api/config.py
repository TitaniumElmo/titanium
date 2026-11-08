"""Configuração da API, lida das variáveis de ambiente (ver .env.example)."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

PASTA_UPLOADS = Path(os.getenv("HEITOR_UPLOADS", RAIZ / "data" / "uploads"))
PASTA_EXEMPLOS = RAIZ / "heitor" / "exemplos"
FICHA_EXEMPLO = PASTA_EXEMPLOS / "fichas_exemplo.csv"

# "1" força os stubs mesmo que o código real da Sofia/Gustavo exista.
FORCAR_STUBS = os.getenv("HEITOR_STUBS") == "1"

# Pausa entre eventos do agente falso, para o log ao vivo ficar visível na tela.
STUB_ATRASO_S = float(os.getenv("HEITOR_STUB_ATRASO", "0.3"))

# Gatilho 1 (vigia da pasta). Drive tem prioridade sobre a pasta local.
DRIVE_PASTA = os.getenv("HEITOR_DRIVE_PASTA") or None
DRIVE_CREDENCIAIS = os.path.expanduser(os.getenv("HEITOR_DRIVE_CREDENCIAIS", "~/.config/heitor/drive.json"))


def _credenciais_do_segredo() -> None:
    """No deploy (Hugging Face Spaces) não há arquivo: a chave da conta de serviço vem inteira no
    segredo HEITOR_DRIVE_CREDENCIAIS_JSON e é gravada num arquivo só do processo (permissão 600)."""
    global DRIVE_CREDENCIAIS
    conteudo = os.getenv("HEITOR_DRIVE_CREDENCIAIS_JSON", "").strip()
    if not conteudo:
        return
    import tempfile

    fd, caminho = tempfile.mkstemp(prefix="heitor-drive-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(conteudo)
    os.chmod(caminho, 0o600)
    DRIVE_CREDENCIAIS = caminho


_credenciais_do_segredo()
FONTE_PASTA = os.getenv("HEITOR_FONTE_PASTA") or None
VIGIA_INTERVALO_S = float(os.getenv("HEITOR_VIGIA_INTERVALO", "10"))

# Gatilho 2 sem vigia: a cada quantos segundos a cobrança de prazos vencidos roda.
COBRANCA_INTERVALO_S = float(os.getenv("HEITOR_COBRANCA_INTERVALO", "60"))

# Segurança (heitor/api/seguranca.py). Lidas na hora, para o .env e os testes valerem.
EXTENSOES_UPLOAD = {".csv", ".pdf", ".jpg", ".jpeg", ".png", ".webp"}  # PDF: ficha arquivada (#24)


def token_admin() -> str:
    """Token das rotas de administração; vazio = liberadas (desenvolvimento)."""
    return os.getenv("HEITOR_TOKEN_ADMIN", "").strip()


def modo_demo() -> bool:
    """POST /demo/reset só existe com HEITOR_DEMO=1."""
    return os.getenv("HEITOR_DEMO", "").strip().lower() in ("1", "true", "sim", "on")


def max_upload_bytes() -> int:
    return int(float(os.getenv("HEITOR_MAX_UPLOAD_MB", "15")) * 1024 * 1024)


def max_arquivos() -> int:
    return int(os.getenv("HEITOR_MAX_ARQUIVOS", "20"))
