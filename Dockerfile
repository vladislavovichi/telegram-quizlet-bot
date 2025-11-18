FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY tests ./tests

COPY pyproject.toml ./

RUN python -c "import tomllib; from pathlib import Path; data=tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8')); deps=data.get('project', {}).get('dependencies', []); print('\n'.join(deps))" > /tmp/requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt

COPY . .

ENV APP_ENV=production

CMD ["python3", "main.py"]
