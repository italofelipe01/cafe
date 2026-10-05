# Imagem do Copa Pronta para nuvem ou para um servidor com Docker.
#
# O mesmo run.py da instalação local: Waitress, migrations aplicadas na subida
# (AUTO_MIGRATE, padrão em produção) e catálogo semeado só no banco vazio.
# Detalhes em docs/DEPLOY.md.

FROM python:3.13-slim

# PORT, e não APP_PORT: é a variável que Render, Railway, Heroku e Cloud Run
# sobrescrevem; um APP_PORT fixado aqui venceria a da plataforma. O banco padrão
# é SQLite no volume /data; para PostgreSQL, sobrescreva DATABASE_URL.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite:////data/copa.db

WORKDIR /app

# Dependências antes do código: mudar só o código não reinstala nada.
COPY requirements.txt requirements-postgres.txt ./
RUN pip install -r requirements-postgres.txt

COPY app ./app
COPY migrations ./migrations
COPY config.py run.py pyproject.toml ./

RUN useradd --create-home --uid 1000 copa \
    && mkdir -p /data \
    && chown copa:copa /data

USER copa
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"

CMD ["python", "run.py"]
