# CodeBot-only image: people ships no Dockerfile of its own -- unlike
# openstates-scrapers/core/api-v3 (each of which already had one for a real
# production purpose), this is a data-only repo with nothing to deploy. This
# file exists purely to pin the Python 3.9 + poetry env this repo's own CI
# (.github/workflows/lint-yaml.yml) already runs on, scoped to
# .codebot/test.sh. Build context is the repo root (see test.sh).
FROM python:3.9-slim
LABEL maintainer="Digital Democracy Project"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONIOENCODING='utf-8'
ENV LANG='C.UTF-8'

RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      build-essential \
      git \
    && pip --no-cache-dir --disable-pip-version-check install poetry

WORKDIR /opt/people
ADD pyproject.toml poetry.lock /opt/people/
# --no-root: this repo has no installable package (pyproject.toml names one,
# "ospeople", but there's no ospeople/ source dir behind it -- it's a
# data-only repo). Its own CI never installs the root either. One install
# call is enough here: unlike scrapers/core, there's no source package to
# pick up in a second pass once the full tree is added below.
RUN poetry install --no-root -q \
    && rm -rf /root/.cache/pypoetry/cache /root/.cache/pypoetry/artifacts/ \
    && apt-get purge -y -qq build-essential \
    && apt-get autoremove -y -qq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ADD . /opt/people

ENTRYPOINT ["poetry", "run"]
