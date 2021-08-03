#! /usr/bin/env bash
set -xe

docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA-amd64

if [[ $CI_COMMIT_TAG =~ ^v.*$ ]]; then
    docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA-amd64 $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG-amd64
    docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG-amd64
    docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA-amd64 $CI_REGISTRY_IMAGE:latest-amd64
    docker push $CI_REGISTRY_IMAGE:latest-amd64
fi
