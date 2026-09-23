#!/bin/sh
set -e

echo "configuring somef..."
printf "%s\n" \
    "${GITHUB_API_TOKEN:-}" \
    "${GITLAB_API_TOKEN:-}" \
    "${CODEBERG_TOKEN:-}" \
    "${BITBUCKET_API_TOKEN:-}" \
    "${BITBUCKET_EMAIL:-}" \
    "${SOMEF_DESCRIPTION_MODEL:-}" \
    "${SOMEF_INVOCATION_MODEL:-}" \
    "${SOMEF_INSTALLATION_MODEL:-}" \
    "${SOMEF_CITATION_MODEL:-}" \
    "${SOMEF_BASE_URI:-}" \
    "${SOMEF_DOWNLOAD_LIMIT_MB:-1000}" \
    | somef configure

exec "$@"
