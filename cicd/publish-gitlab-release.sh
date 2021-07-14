#! /usr/bin/env sh

set -e

echo "VARIABLES"
echo "CI_COMMIT_TAG=${CI_COMMIT_TAG}"
echo "CI_API_V4_URL=${CI_API_V4_URL}"
echo "CI_PROJECT_ID=${CI_PROJECT_ID}"
echo "CI_PIPELINE_ID=${CI_PIPELINE_ID}"
echo "CI_PROJECT_URL=${CI_PROJECT_URL}"

# The release notes for this version should be the first line of the CHANGELOG.
if [[ $(head -n 1 CHANGELOG.md) == "# ${CI_COMMIT_TAG}" ]]; then
    # Extract all of the text until the next header.
    i=0
    first=1
    while read l; do
        i=$(( $i + 1 ))
        if [[ $l =~ ^#.*$ ]]; then
            if [[ $first == 0 ]]; then
                break
            fi
            first=0
        fi
    done < CHANGELOG.md
    # i is now the index of the line of the second header.

    changes=$(head -n $(( $i - 1 )) CHANGELOG.md | tail -n $(( $i - 3 )))
fi

if [[ "$changes" == "" ]]; then
    echo "No release notes found!"
    exit 1
fi

url="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases"
data="
{
    \"name\": \"${CI_COMMIT_TAG}\",
    \"tag_name\": \"${CI_COMMIT_TAG}\",
    \"description\": \"${changes}\"
}
"

echo "URL:"
echo "$url"
echo "DATA:"
echo "$data"

curl \
    --header 'Content-Type: application/json' \
    --header "PRIVATE-TOKEN: ${RELEASE_PUBLISH_TOKEN}" \
    --data "$data" \
    --request POST \
    $url
