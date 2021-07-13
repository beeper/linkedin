FROM python:3.9.6-alpine3.14

ARG TARGETARCH=amd64

RUN apk add --no-cache \
      python3 \
      py3-pip \
      py3-setuptools \
      py3-wheel \
      cargo \
      openssl-dev \
      py3-virtualenv \
      py3-pillow \
      py3-aiohttp \
      py3-magic \
      py3-ruamel.yaml \
      py3-commonmark \
      py3-prometheus-client \
      # Other dependencies \
      ca-certificates \
      su-exec \
      # encryption \
      py3-olm \
      py3-cffi \
      py3-pycryptodome \
      py3-cryptography \
      py3-unpaddedbase64 \
      py3-future \
      bash \
      curl \
      jq \
      olm \
      yq \
      # Pillow (TODO can these move to the .build-deps?)\
      tiff-dev \
      jpeg-dev \
      openjpeg-dev \
      zlib-dev \
      freetype-dev \
      lcms2-dev \
      libwebp-dev \
      tcl-dev \
      tk-dev \
      harfbuzz-dev \
      fribidi-dev \
      libimagequant-dev \
      libxcb-dev \
      libpng-dev

# COPY requirements.txt /opt/linkedin-matrix/requirements.txt
# WORKDIR /opt/linkedin-matrix
# RUN apk add --virtual .build-deps python3-dev libffi-dev build-base \
#  && pip3 install -r requirements.txt --extra-index-url https://gitlab.matrix.org/api/v4/projects/27/packages/pypi/simple \
#  && apk del .build-deps

# Use the actual package once poetry gets into a release
# https://pkgs.alpinelinux.org/package/edge/testing/x86_64/poetry
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.1.6

RUN apk add --virtual .build-deps python3-dev libffi-dev build-base

# System deps:
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /opt/linkedin-matrix
COPY . /opt/linkedin-matrix/

RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi -E images -E e2be

RUN apk del .build-deps

# This doesn't make the image smaller, but it's needed so that the `version` command works properly
# RUN cp linkedin_matrix/example-config.yaml . && rm -rf linkedin_matrix

VOLUME /data
ENV UID=1337 GID=1337

CMD ["/opt/linkedin-matrix/docker-run.sh"]
