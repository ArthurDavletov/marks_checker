set -e

host = "MYSQL"
port = "3306"
cmd = "$@"

>&2 echo "[entrypoint.sh] Check MySQL for available..."

until curl http://"$host":"$port"; do
  >&2 echo "MySQL is unavailable - sleeping"
  sleep 1
done

>&2 echo "MySQL is up - executing command"

exec $cmd