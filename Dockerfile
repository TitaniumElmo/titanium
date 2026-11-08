# API do Heitor para o Hugging Face Spaces (SDK Docker; a porta 7860 é a padrão do Spaces).
# Teste local:
#   docker build --build-arg CAEPI_URL=<url do .gz> -t heitor .
#   docker run -p 7860:7860 --env-file .env heitor   ->  http://localhost:7860
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEITOR_UPLOADS=/tmp/heitor-uploads \
    PORT=7860

# O Spaces roda o container com o usuário 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Base CAEPI (144 MB, fora do Git): baixada compactada do dataset público no Hugging Face.
# Sem a URL, a API sobe sem a base (as regras avisam no log).
ARG CAEPI_URL=https://huggingface.co/datasets/ElmoAgent/caepi/resolve/main/RelatorioCA_20261107_143153.csv.gz
RUN mkdir -p dados && if [ -n "$CAEPI_URL" ]; then python -c "\
import gzip, shutil, sys, urllib.request; \
url = sys.argv[1]; nome = url.rsplit('/', 1)[-1].removesuffix('.gz'); \
resp = urllib.request.urlopen(url, timeout=300); \
destino = open('dados/' + nome, 'wb'); \
shutil.copyfileobj(gzip.GzipFile(fileobj=resp) if url.endswith('.gz') else resp, destino); \
destino.close(); print('base CAEPI:', nome)" "$CAEPI_URL"; fi

COPY --chown=user . .
USER user
EXPOSE 7860
CMD ["sh", "-c", "uvicorn heitor.api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
