"""Fontes de fichas que o vigia observa (gatilho 1).

Uma fonte é uma pasta. O técnico só faz o trabalho normal dele (põe um CSV
ou a foto da ficha na pasta, ou edita uma planilha que está lá) e o Heitor
percebe sozinho. O Heitor só LÊ a fonte: nunca escreve, renomeia ou apaga.

- PastaLocal: uma pasta no disco. Para testes e como reserva sem internet.
- PastaDrive: uma pasta do Google Drive, lida por uma conta de serviço com
  permissão de Leitor (HEITOR_DRIVE_CREDENCIAIS + HEITOR_DRIVE_PASTA).

Cada arquivo tem uma `assinatura` que muda quando o conteúdo muda; é assim
que o vigia sabe o que é novo ou alterado sem baixar tudo de novo.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

log = logging.getLogger("heitor.fontes")

EXTENSOES_FICHA = {".csv": "planilha", ".jpg": "foto", ".jpeg": "foto", ".png": "foto", ".webp": "foto"}
MIME_PLANILHA_GOOGLE = "application/vnd.google-apps.spreadsheet"
_MIME_EXTENSAO = {"text/csv": ".csv", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@dataclass(frozen=True)
class ArquivoFonte:
    id: str  # estável enquanto o arquivo existir (caminho local ou id do Drive)
    nome: str  # nome com extensão, como será salvo para leitura
    assinatura: str  # muda quando o conteúdo muda
    tipo: str  # "planilha" ou "foto"
    exportar: bool = False  # planilha do Google: baixa exportando a primeira aba em CSV
    # Planilha do Google: a versão muda NA HORA da edição, antes de o CSV exportado mudar.
    # O vigia usa para avisar "edição detectada" sem esperar o conteúdo.
    versao: Optional[str] = None


class Fonte(Protocol):
    descricao: str

    def listar(self) -> list[ArquivoFonte]: ...

    def baixar(self, arquivo: ArquivoFonte, destino: Path) -> Path: ...


def _nome_seguro(nome: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", Path(nome).name).strip() or "arquivo"


# ---------------------------------------------------------------------------
# Pasta local
# ---------------------------------------------------------------------------


class PastaLocal:
    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)
        self.descricao = f"pasta local {self.caminho}"

    def listar(self) -> list[ArquivoFonte]:
        if not self.caminho.is_dir():
            raise FileNotFoundError(f"pasta não encontrada: {self.caminho}")
        arquivos = []
        for p in sorted(self.caminho.iterdir()):
            tipo = EXTENSOES_FICHA.get(p.suffix.lower())
            if not tipo or not p.is_file() or p.name.startswith("."):
                continue
            arquivos.append(ArquivoFonte(id=str(p), nome=p.name, assinatura=_md5(p), tipo=tipo))
        return arquivos

    def baixar(self, arquivo: ArquivoFonte, destino: Path) -> Path:
        destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / _nome_seguro(arquivo.nome)
        alvo.write_bytes(Path(arquivo.id).read_bytes())
        return alvo


def _md5(caminho: Path) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

_API = "https://www.googleapis.com/drive/v3/files"
_ESCOPO = ["https://www.googleapis.com/auth/drive.readonly"]


class PastaDrive:
    def __init__(self, pasta_id: str, credenciais: Path | str, timeout_s: float = 30):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        cred = service_account.Credentials.from_service_account_file(str(credenciais), scopes=_ESCOPO)
        self._sessao = AuthorizedSession(cred)
        self._timeout = timeout_s
        self.pasta_id = pasta_id
        self.conta = cred.service_account_email
        self.descricao = f"pasta do Drive {pasta_id}"
        # Planilha do Google: id -> (versão, quando essa versão foi vista, md5 do CSV, CSV)
        self._planilhas: dict[str, tuple[str, float, str, bytes]] = {}

    # Depois que a versão de uma planilha muda, o CSV exportado pode demorar a
    # refletir a edição (visto no teste real: a versão mudou e a exportação seguiu
    # antiga por ~1 min). Durante esta janela a planilha é exportada a cada
    # listagem e a assinatura é o conteúdo; depois, reaproveita o último conteúdo.
    JANELA_PLANILHA_S = 120.0

    def _get(self, url: str, **params):
        r = self._sessao.get(url, params=params, timeout=self._timeout)
        if r.status_code == 404:
            raise FileNotFoundError(
                f"o Drive não achou {url.rsplit('/', 1)[-1]}: a pasta foi compartilhada com {self.conta}?"
            )
        r.raise_for_status()
        return r

    def listar(self) -> list[ArquivoFonte]:
        arquivos, pagina = [], None
        while True:
            params = {
                "q": f"'{self.pasta_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum, version)",
                "pageSize": 1000,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if pagina:
                params["pageToken"] = pagina
            dados = self._get(_API, **params).json()
            for f in dados.get("files", []):
                arquivo = self._converter(f)
                if arquivo and arquivo.exportar:
                    arquivo = self._assinar_pelo_conteudo(arquivo)
                if arquivo:
                    arquivos.append(arquivo)
            pagina = dados.get("nextPageToken")
            if not pagina:
                return sorted(arquivos, key=lambda a: a.nome)

    def _assinar_pelo_conteudo(self, arquivo: ArquivoFonte) -> ArquivoFonte:
        """Planilha do Google: a assinatura é o md5 do CSV exportado, não a versão."""
        versao, agora = arquivo.assinatura, time.monotonic()
        anterior = self._planilhas.get(arquivo.id)
        if anterior and anterior[0] == versao and agora - anterior[1] > self.JANELA_PLANILHA_S:
            md5 = anterior[2]  # versão parada há tempo: o conteúdo já assentou
        else:
            conteudo = self._get(f"{_API}/{arquivo.id}/export", mimeType="text/csv").content
            md5 = hashlib.md5(conteudo).hexdigest()
            visto_em = anterior[1] if anterior and anterior[0] == versao else agora
            self._planilhas[arquivo.id] = (versao, visto_em, md5, conteudo)
        return ArquivoFonte(arquivo.id, arquivo.nome, f"conteudo:{md5}", arquivo.tipo, exportar=True, versao=versao)

    @staticmethod
    def _converter(f: dict) -> Optional[ArquivoFonte]:
        mime, nome = f.get("mimeType", ""), f.get("name", "")
        # Planilha do Google não tem md5: a versão muda a cada edição.
        assinatura = f.get("md5Checksum") or f"{f.get('version')}|{f.get('modifiedTime')}"
        if mime == MIME_PLANILHA_GOOGLE:
            return ArquivoFonte(f["id"], f"{Path(nome).stem or 'planilha'}.csv", assinatura, "planilha", exportar=True)
        ext = Path(nome).suffix.lower()
        if ext not in EXTENSOES_FICHA:
            ext = _MIME_EXTENSAO.get(mime, "")
            nome = f"{nome}{ext}"
        tipo = EXTENSOES_FICHA.get(ext)
        return ArquivoFonte(f["id"], nome, assinatura, tipo) if tipo else None

    def baixar(self, arquivo: ArquivoFonte, destino: Path) -> Path:
        destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / _nome_seguro(arquivo.nome)
        guardado = self._planilhas.get(arquivo.id)
        if arquivo.exportar and guardado and arquivo.assinatura == f"conteudo:{guardado[2]}":
            conteudo = guardado[3]  # exatamente o conteúdo que gerou a assinatura
        elif arquivo.exportar:
            conteudo = self._get(f"{_API}/{arquivo.id}/export", mimeType="text/csv").content
        else:
            conteudo = self._get(f"{_API}/{arquivo.id}", alt="media", supportsAllDrives="true").content
        alvo.write_bytes(conteudo)
        return alvo
