FROM docker.io/alpine:3.19

ARG TARGETARCH=amd64

RUN apk add --no-cache \
    python3 py3-pip py3-setuptools py3-wheel \
    #py3-pillow \
    py3-aiohttp \
    py3-magic \
    py3-ruamel.yaml \
    py3-commonmark \
    py3-prometheus-client \
    py3-olm \
    py3-cffi \
    py3-pycryptodome \
    py3-unpaddedbase64 \
    py3-future \
    py3-aiohttp-socks \
    py3-pysocks \
    ca-certificates \
    su-exec \
    bash \
    curl \
    git \
    jq \
    yq

COPY requirements.txt /opt/linkedin-matrix/requirements.txt
COPY optional-requirements.txt /opt/linkedin-matrix/optional-requirements.txt
WORKDIR /opt/linkedin-matrix

RUN apk add --virtual .build-deps python3-dev libffi-dev build-base \
    && pip3 install --break-system-packages --no-cache-dir -r requirements.txt -r optional-requirements.txt \
    && apk del .build-deps

COPY . /opt/linkedin-matrix
RUN apk add --no-cache git && pip3 install --break-system-packages --no-cache-dir .[e2be] && apk del git \
    # This doesn't make the image smaller, but it's needed so that the `version` command works properly
    && cp linkedin_matrix/example-config.yaml . && rm -rf linkedin_matrix .git build

VOLUME /data
ENV UID=1337 GID=1337

CMD ["/opt/linkedin-matrix/docker-run.sh"]
