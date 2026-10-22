#!/bin/sh
i=0
until ollama list >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 30 ]; then
    echo "Ollama did not start" >&2
    exit 1
  fi
  sleep 1
done
ollama pull embeddinggemma
if [ -n "$PULL_CHAT_MODEL" ]; then
  ollama pull "$PULL_CHAT_MODEL"
fi
