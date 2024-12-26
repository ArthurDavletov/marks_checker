#!/bin/sh

set -e

# if [ -f ".env" ]; then
#   export $(grep -v '^#' .env | xargs)
# fi

host="mysql"
port="3306"
user="user"
password="jQczw7h6MxD438USga"
cmd="$@"

>&2 echo "[entrypoint.sh] Check MySQL for available..."

until mysqladmin ping -h"$host" -P"$port" -u"$user" --password="$password" --silent; do
  >&2 echo "[entrypoint.sh] MySQL is unavailable - sleeping"
  sleep 1
done

>&2 echo "[entrypoint.sh] MySQL is up - executing command"

exec $cmd