import os
import tempfile

# Antes de importar a API: stubs determinísticos, sem pausa, uploads em pasta temporária.
os.environ["HEITOR_STUBS"] = "1"
os.environ["HEITOR_STUB_ATRASO"] = "0"
os.environ["HEITOR_UPLOADS"] = tempfile.mkdtemp(prefix="heitor-uploads-")
# Vazias (e não apagadas): o load_dotenv() da API não sobrescreve variável que
# já existe, então o .env de quem roda os testes não liga e-mail nem o Drive real.
for var in ("SMTP_HOST", "HEITOR_EMAIL_TECNICO", "HEITOR_EMAIL_RH", "HEITOR_DRIVE_PASTA", "HEITOR_FONTE_PASTA",
            "HEITOR_NOME_NO_EMAIL"):
    os.environ[var] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from heitor.api.estado import estado  # noqa: E402
from heitor.api.main import app  # noqa: E402


@pytest.fixture
def client():
    estado.limpar()
    with TestClient(app) as c:
        yield c
