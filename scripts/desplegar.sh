#!/usr/bin/env bash
# Publica la versión actual (último commit de Todo_bot) en producción.
#
# Vercel despliega desde el repo Back-bot y Netlify desde Front-bot (rama master).
# Este script copia backend/ y frontend/ del último commit a esos repos y hace
# un commit normal encima de su historia (sin force-push).
#
# Uso (Git Bash, desde la raíz del repo):
#   bash scripts/desplegar.sh
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
SHA="$(git -C "$REPO" rev-parse --short HEAD)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -n "$(git -C "$REPO" status --porcelain -- backend frontend)" ]; then
  echo "Hay cambios sin commitear en backend/ o frontend/: se publica el último commit ($SHA)."
fi

publicar() {  # $1 = carpeta en Todo_bot, $2 = repo de despliegue
  local carpeta="$1" destino="$TMP/$2"
  git clone -q --branch master "https://github.com/MauroVillagra1/$2.git" "$destino"
  (cd "$destino" && git ls-files -z | xargs -0 rm -f)
  git -C "$REPO" archive HEAD "$carpeta" | tar -x -C "$TMP"
  cp -a "$TMP/$carpeta/." "$destino/"
  rm -rf "$TMP/$carpeta"

  cd "$destino"
  git add -A
  if git status --porcelain | grep -qiE '(^|/)\.env$'; then
    echo "ERROR: se iba a subir un .env a $2. Cancelado." >&2
    exit 1
  fi
  if git diff --cached --quiet; then
    echo "$2: ya estaba al día."
  else
    git commit -q -m "Sincroniza con Todo_bot $SHA"
    git push -q origin master
    echo "$2: publicado ($SHA)."
  fi
  cd "$REPO"
}

publicar backend Back-bot    # → Vercel (API)
publicar frontend Front-bot  # → Netlify (web)
echo "Listo. Vercel y Netlify tardan 1-2 minutos en desplegar."
