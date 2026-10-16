#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Aplicando migrations do banco..."
  attempt=1
  while [ "$attempt" -le 30 ]; do
    if alembic upgrade head; then
      echo "Migrations aplicadas com sucesso."
      break
    fi

    if [ "$attempt" -eq 30 ]; then
      echo "ERRO: não foi possível aplicar as migrations após 30 tentativas." >&2
      exit 1
    fi

    echo "Banco ainda indisponível; nova tentativa em 2s (${attempt}/30)..."
    attempt=$((attempt + 1))
    sleep 2
  done
fi

exec "$@"
