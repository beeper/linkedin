FROM python:3.9.6-alpine3.14

ARG TARGETARCH=amd64

RUN apk add --no-cache \
      bash \
      ca-certificates \
      curl \
      jq \
      libmagic \
      python3 \
      su-exec \
      yq

# Use the actual package once poetry gets into a release
# https://pkgs.alpinelinux.org/package/edge/testing/x86_64/poetry
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.1.6

WORKDIR /opt/linkedin-matrix
COPY . /opt/linkedin-matrix/

RUN apk add --virtual .build-deps \
      py3-pip \
      python3-dev \
      libffi-dev \
      cargo \
      build-base \
      openssl-dev \
      # Pillow \
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
      libpng-dev \
 && pip install "poetry==$POETRY_VERSION" \
 && poetry config virtualenvs.create false \
 && poetry install --no-dev --no-interaction --no-ansi -E images -E e2be \
 && apk del .build-deps

VOLUME /data
ENV UID=1337 GID=1337

CMD ["/opt/linkedin-matrix/docker-run.sh"]
