FROM docker.io/alpine:3.14

ARG TARGETARCH=amd64

RUN apk add --no-cache \
      python3 py3-pip py3-setuptools py3-wheel \
      py3-pillow \
      py3-aiohttp \
      py3-magic \
      py3-ruamel.yaml \
      py3-commonmark \
      py3-paho-mqtt \
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

COPY docker-requirements.txt /opt/linkedin-matrix/requirements.txt
WORKDIR /opt/linkedin-matrix

RUN apk add --virtual .build-deps python3-dev libffi-dev build-base \
 && pip3 install linkedin-messaging==0.5.1 \
 && pip3 install -r requirements.txt \
 && apk del .build-deps

COPY . /opt/linkedin-matrix

VOLUME /data
ENV UID=1337 GID=1337

CMD ["/opt/linkedin-matrix/docker-run.sh"]
