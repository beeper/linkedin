FROM alpine:3.20

ENV UID=1337 \
    GID=1337

RUN apk add --no-cache ffmpeg su-exec ca-certificates bash jq curl yq-go

ARG EXECUTABLE=./cmd/linkedin-matrix
COPY $EXECUTABLE /usr/bin/linkedin-matrix
COPY ./docker-run.sh /docker-run.sh
ENV BRIDGEV2=1
VOLUME /data
WORKDIR /data

CMD ["/docker-run.sh"]
