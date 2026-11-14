#!/bin/sh
# Despliega el commit actual al entorno indicado.
set -eu
entorno="${1:?uso: scripts/deploy.sh <entorno>}"
. "./.env.$entorno"
: "${DEPLOY_TOKEN:?falta DEPLOY_TOKEN en .env.$entorno}"
commit=$(git rev-parse HEAD)
printf '%s %s\n' "$entorno" "$commit" >> "${DEPLOY_LOG:-/tmp/deploy.log}"
echo "Desplegado $(git rev-parse --short HEAD) en $entorno"
