# A base e pinada por digest, nao so pela tag. A tag `3.11-slim` e movel: o
# mesmo commit produzia imagens diferentes conforme o dia do build, e o cache
# do buildx (`cache-from: type=gha`) podia reaproveitar camadas antigas, ja com
# CVEs corrigidas a montante. O pin torna o build reproduzivel e a atualizacao
# da base um commit explicito e revisavel.
#
# Para atualizar:
#   docker pull python:3.11-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim
# ─── Stage 1: build das dependências ─────────────────────────────────────────
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS builder

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# ─── Stage 2: imagem final (slim, non-root) ──────────────────────────────────
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Usuário sem privilégios
RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /install /usr/local
COPY app/ ./app/

# setuptools e wheel são ferramentas de build e não são usadas em runtime. Remove
# da imagem final para reduzir a superfície de ataque: e delas que vinham as CVEs
# de jaraco.context e wheel apontadas pelo scan.
RUN pip uninstall -y setuptools wheel pip 2>/dev/null || true

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health/live').status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
