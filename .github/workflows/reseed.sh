#!/usr/bin/env bash
set -euo pipefail

cd /root/projects/vkmax-mobilization
api=https://vkmax.k1rles.ru/api
auth="Authorization: Bearer $(sed -n 's/^API_TEST_TOKEN=//p' .env)"
json="Content-Type: application/json"

docker compose exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "/root/zheka-backup-$(date +%F-%H%M).sql.gz"
docker compose down -v --remove-orphans
docker compose up -d --remove-orphans
for _ in $(seq 60); do curl -fsS -o /dev/null "$api/healthcheck" && break; sleep 5; done
docker compose run --rm api python -m zheka.seed

curl -fsS -H "$auth" -H "$json" -d '{"version":"1.0"}' "$api/me/consent" > /dev/null
demo=$(curl -fsS -H "$auth" -H "$json" -d '{"number":5}' "$api/demo/activate")
request=$(curl -fsS -H "$auth" -H "$json" -d '{"category":"leak","description":"Течет кран в ванной, проверка API"}' "$api/requests")
org=$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])["org"]["org_id"])' "$demo")
foreign=$(docker compose exec -T database sh -c "psql -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\" -tAc 'select r.id from requests r join houses h on h.id = r.house_id where h.org_id <> $org and r.author_user_id is not null order by r.id limit 1'")

python3 - "$demo" "$request" "$foreign" <<'PY'
import json, sys
demo, request = json.loads(sys.argv[1]), json.loads(sys.argv[2])
print("test_data:")
print(f"  house_id: {demo['residency']['house_id']}")
print(f"  flat_id: {demo['residency']['flat_id']}")
print(f"  request_id: {request['id']}")
print(f"  foreign_request_id: {sys.argv[3].strip()}")
PY
