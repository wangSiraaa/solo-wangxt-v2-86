#!/usr/bin/env bash
# 一键启动：PostgreSQL（用户态）+ Django 迁移/案例 + 前端构建 + 开发服务器
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PGBIN="$ROOT/.pgsql/bin"
PGDATA="$ROOT/.pgsql/data"
SOCKDIR=/tmp/pgrun

# 1) PostgreSQL
mkdir -p "$SOCKDIR"
if ! "$PGBIN/pg_ctl" -D "$PGDATA" status > /dev/null 2>&1; then
  "$PGBIN/pg_ctl" -D "$PGDATA" -l "$ROOT/.pgsql/pg.log" \
    -o "-k $SOCKDIR -p 5432 -c listen_addresses=127.0.0.1" start
fi
python3 - <<'PY'
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5432, user='postgres', dbname='postgres')
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='revrec'")
if not cur.fetchone():
    cur.execute('CREATE DATABASE revrec')
conn.close()
PY

# 2) 后端：迁移 + 案例数据
cd "$ROOT/server"
python3 manage.py migrate --noinput
python3 manage.py seed_demo

# 3) 前端：构建（已有产物则跳过，强制重建用 npm run build）
if [ ! -f "$ROOT/server/frontend_dist/index.html" ]; then
  cd "$ROOT/client" && npm install && npm run build && cd "$ROOT/server"
fi

# 4) 启动 Django
echo "==> http://127.0.0.1:8000/"
exec python3 manage.py runserver 127.0.0.1:8000
