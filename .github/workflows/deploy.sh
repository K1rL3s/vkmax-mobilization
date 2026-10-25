#!/usr/bin/env bash
set -euo pipefail

cd /root/projects/vkmax-mobilization
export BUILD_COMMIT=$(git rev-parse HEAD)

replicas() {
    docker ps -aq \
        --filter label=com.docker.compose.project=vkmax-mobilization \
        --filter label=com.docker.compose.service="$1" \
        --filter label=com.docker.compose.oneoff=False
}

roll() {
    local old new
    old=$(replicas "$1")
    if ! docker compose up -d --no-deps --no-recreate --wait --wait-timeout 180 \
        --scale "$1=$(($(wc -w <<< "$old") + 1))" "$1"; then
        new=$(replicas "$1" | grep -vxF "$old" || true)
        [ -z "$new" ] || docker rm -f $new
        return 1
    fi
    sleep 2
    if [ -n "$old" ]; then
        docker stop $old
        docker rm $old
    fi
}

docker compose build
docker compose run --rm migrations
roll api
roll web
docker compose up -d --remove-orphans
cmp -s nginx/nginx.conf <(docker compose exec -T nginx cat /etc/nginx/nginx.conf) || docker compose restart nginx
docker compose exec -T nginx nginx -s reload
docker image prune -f
