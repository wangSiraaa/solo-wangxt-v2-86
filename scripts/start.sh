#!/usr/bin/env bash
# 一键启动：用户态 PostgreSQL（unix socket /tmp:5439）+ Django（:8000）
# PostgreSQL 二进制与数据目录位于 $HOME/pgsql、$HOME/pgdata（免 root 解包安装）
set -euo pipefail

PGBIN="$HOME/pgsql/usr/lib/postgresql/15/bin"
PGDATA="$HOME/pgdata"
BACKEND_DIR="$(cd "$(dirname "$0")/../backend" && pwd)"

if [ ! -x "$PGBIN/postgres" ]; then
  echo "未找到 PostgreSQL：$PGBIN/postgres"
  echo "请按 README 的「环境准备」一节安装（免 root）。"
  exit 1
fi

# 首次运行：初始化数据簇
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  mkdir -p "$PGDATA"
  "$PGBIN/initdb" -D "$PGDATA" -U postgres --auth=trust >/dev/null
  echo "port = 5439" >> "$PGDATA/postgresql.conf"
  echo "listen_addresses = ''" >> "$PGDATA/postgresql.conf"
  echo "unix_socket_directories = '/tmp'" >> "$PGDATA/postgresql.conf"
fi

# 启动数据库（已启动则跳过）
if ! "$PGBIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
  "$PGBIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/pg.log" -w start
fi
"$PGBIN/psql" -h /tmp -p 5439 -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='revenue'" \
  | grep -q 1 || "$PGBIN/createdb" -h /tmp -p 5439 -U postgres revenue

cd "$BACKEND_DIR"
python3 manage.py migrate --noinput
python3 manage.py seed_demo
python3 manage.py verify_demo
echo
echo "应用已启动： http://127.0.0.1:8000/"
exec python3 manage.py runserver 127.0.0.1:8000
