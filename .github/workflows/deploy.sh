#!/usr/bin/env bash
set -euo pipefail

cd /root/projects/vkmax-mobilization
git fetch origin
git merge --ff-only origin/master
export BUILD_COMMIT=$(git rev-parse HEAD)
docker compose up -d --build --remove-orphans
docker compose restart nginx
docker image prune -f
