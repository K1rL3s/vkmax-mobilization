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

curl -fsS -H "$auth" -H "$json" -d '{"version":"1.2"}' "$api/me/consent" > /dev/null
demo=$(curl -fsS -H "$auth" -H "$json" -d '{"number":5}' "$api/demo/activate")
request=$(curl -fsS -H "$auth" -H "$json" -d '{"category":"leak","description":"Течет кран в ванной, проверка API","place":"flat"}' "$api/requests")
org=$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])["org"]["org_id"])' "$demo")
foreign=$(docker compose exec -T database sh -c "psql -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\" -tAc 'select r.id from requests r join houses h on h.id = r.house_id where h.org_id <> $org and r.author_user_id is not null order by r.id limit 1'")

python3 - "$demo" "$request" "$foreign" <<'PY'
import json, re, sys
from pathlib import Path
demo, request = json.loads(sys.argv[1]), json.loads(sys.argv[2])
fresh = {
    "house_id": str(demo["residency"]["house_id"]),
    "flat_id": str(demo["residency"]["flat_id"]),
    "request_id": str(request["id"]),
    "foreign_request_id": sys.argv[3].strip(),
}
for key, value in fresh.items():
    print(f"{key}: {value}")
committed = {
    (("foreign_" if check.endswith("_foreign") else "") + key.replace("X-House-Id", "house_id"), value)
    for check, block in re.findall(r"^  - id: (\w+)\n((?:    .*\n)+)", Path("DATA-API.yaml").read_text(), re.M)
    for key, value in re.findall(r'^ +(\w+_id|X-House-Id): "?(\d+)"?$', block, re.M)
}
if committed != set(fresh.items()):
    sys.exit("DATA-API.yaml ids differ from the new ones: update them and commit")
PY
