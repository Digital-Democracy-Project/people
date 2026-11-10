# CodeBot-only image: people ships no Dockerfile of its own -- unlike
# openstates-scrapers/core/api-v3 (each of which already had one for a real
# production purpose), this is a data-only repo with nothing to deploy. This
# file exists purely to pin the Python 3.13 + uv env this repo's own CI
# (.github/workflows/lint-yaml.yml) already runs on, scoped to
# .codebot/test.sh. Build context is the repo root (see test.sh).
# Upstream moved from Poetry to uv on 2026-11-05 (poetry.lock removed,
# requires-python >=3.13); this follows it.
FROM python:3.13-slim
LABEL maintainer="Digital Democracy Project"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONIOENCODING='utf-8'
ENV LANG='C.UTF-8'
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends git \
    && pip --no-cache-dir --disable-pip-version-check install uv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/people
ADD pyproject.toml uv.lock /opt/people/
# package = false in pyproject.toml: data-only repo, nothing to install as root.
RUN uv sync --frozen -q && rm -rf /root/.cache/uv

ADD . /opt/people

ENTRYPOINT ["uv", "run", "--frozen"]
