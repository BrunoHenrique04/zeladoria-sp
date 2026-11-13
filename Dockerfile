# syntax=docker/dockerfile:1

# Estágio 1: instala as dependências num venv isolado
FROM python:3.12-slim AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# Estágio 2: imagem final, só com o venv e o código
FROM python:3.12-slim

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="zeladoria-sp" \
      org.opencontainers.image.description="API de ocorrências urbanas de São Paulo" \
      org.opencontainers.image.source="https://github.com/BrunoHenrique04/zeladoria-sp" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT"

# Aplica as correções de segurança do Debian que saíram depois da imagem base
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
