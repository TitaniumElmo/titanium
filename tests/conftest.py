import os
import tempfile

# Antes de importar a API: stubs determinísticos, sem pausa, uploads em pasta temporária.
os.environ["HEITOR_STUBS"] = "1"
os.environ["HEITOR_STUB_ATRASO"] = "0"
os.environ["HEITOR_UPLOADS"] = tempfile.mkdtemp(prefix="heitor-uploads-")
for var in ("SMTP_HOST", "HEITOR_EMAIL_TECNICO", "HEITOR_EMAIL_RH"):
    os.environ.pop(var, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from heitor.api.estado import estado  # noqa: E402
from heitor.api.main import app  # noqa: E402


@pytest.fixture
def client():
    estado.limpar()
    with TestClient(app) as c:
        yield c
