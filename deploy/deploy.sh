#!/usr/bin/env bash
# =============================================================================
# deploy.sh — atualiza produção a partir do git
#
# Idempotente: pode rodar várias vezes sem efeitos colaterais.
# NÃO instala pré-requisitos (Python, Node, Postgres, Nginx) — isso é a
# primeira vez, ver docs/DEPLOY_PRODUCAO.md. Este script é pro "ciclo
# de atualização" depois que tudo já está configurado.
#
# Fluxo:
#   1. git pull
#   2. backend: pip install, alembic upgrade
#   3. frontend: npm ci, npm run build
#   4. restart systemd backend, reload nginx
#
# Rodar como:  sudo -u extrator /opt/extrator-protheus/deploy/deploy.sh
# (Os systemctl precisam de sudo — o script usa sudo para esses dois comandos.)
# =============================================================================
set -euo pipefail

PROJECT_DIR="/opt/extrator-protheus"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BRANCH="${BRANCH:-main}"

cd "$PROJECT_DIR"

echo "========================================"
echo "== Extrator Protheus — Deploy          =="
echo "== $(date '+%Y-%m-%d %H:%M:%S')         "
echo "========================================"

# ---- 1. Puxar última versão ----
echo ""
echo "[1/5] git pull..."
git fetch origin "$BRANCH"
# Mostra os commits novos antes de aplicar (facilita entender o que mudou).
HEAD_ANTES=$(git rev-parse HEAD)
HEAD_NOVO=$(git rev-parse "origin/$BRANCH")
if [ "$HEAD_ANTES" = "$HEAD_NOVO" ]; then
    echo "   → nada novo. HEAD já em $HEAD_ANTES."
else
    echo "   → de $HEAD_ANTES"
    echo "   → pra $HEAD_NOVO"
    echo "   → commits novos:"
    git log --oneline "$HEAD_ANTES..$HEAD_NOVO" | sed 's/^/        /'
    git reset --hard "origin/$BRANCH"
fi

# ---- 2. Backend: deps + migrations ----
echo ""
echo "[2/5] Backend: deps..."
cd "$BACKEND_DIR"
# --disable-pip-version-check e --quiet reduzem ruído.
./.venv/bin/pip install --disable-pip-version-check --quiet -r requirements.txt

echo ""
echo "[3/5] Backend: migrations Alembic..."
./.venv/bin/alembic upgrade head

# ---- 4. Frontend: build ----
echo ""
echo "[4/5] Frontend: build..."
cd "$FRONTEND_DIR"
# npm ci é mais rigoroso que npm install (usa exatamente package-lock.json).
npm ci --silent --no-audit --no-fund
npm run build --silent

# ---- 5. Reload serviços ----
echo ""
echo "[5/5] Reload serviços..."
sudo /bin/systemctl restart extrator-backend
sudo /bin/nginx -t && sudo /bin/systemctl reload nginx

echo ""
echo "✅ Deploy concluído."
echo "   Backend:  $(sudo /bin/systemctl is-active extrator-backend)"
echo "   Nginx:    $(sudo /bin/systemctl is-active nginx)"
echo ""
echo "   Verifique: https://192.168.3.128/"
