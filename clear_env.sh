#!/bin/bash
set +e

if [ ! -f .env ]; then
  echo ".env file not found"
  exit 1
fi

read_env_value() {
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

PROJECT_NAME="$(read_env_value PROJECT_NAME)"
DEPLOY_ENV="$(read_env_value DEPLOY_ENV)"
CONTAINER_INITIALS="$(read_env_value CONTAINER_INITIALS)"

case "$CONTAINER_INITIALS" in
  ""|*'$'*)
    CONTAINER_INITIALS="${PROJECT_NAME}-${DEPLOY_ENV}"
    ;;
esac

if [ -z "${CONTAINER_INITIALS:-}" ]; then
  echo "CONTAINER_INITIALS is not set"
  exit 1
fi

echo "1. STOPPING CONTAINERS"
containers=$(docker ps --filter "name=$CONTAINER_INITIALS" -q)
if [ -n "$containers" ]; then
  docker stop $containers || true
else
  echo "No containers to stop"
fi

echo "2. REMOVING CONTAINERS"
# Remove containers with name containing "$CONTAINER_INITIALS"
containers_all=$(docker ps -a --filter "name=$CONTAINER_INITIALS" -q)
if [ -n "$containers_all" ]; then
  docker rm $containers_all || true
else
  echo "No containers to remove"
fi

echo "3. REMOVING IMAGES."
# Remove images with reference containing "$CONTAINER_INITIALS"
images=$(docker images --filter=reference="${CONTAINER_INITIALS}*" -q)
if [ -n "$images" ]; then
  docker rmi $images || true
else
  echo "No images to remove"
fi

echo "4. REMOVING NETWORKS"
# Remove networks with name containing "$CONTAINER_INITIALS"
networks=$(docker network ls --filter "name=$CONTAINER_INITIALS" -q)
if [ -n "$networks" ]; then
  docker network rm $networks || true
else
  echo "No networks to remove"
fi

echo "5. REMOVING PROJECT VOLUMES"
volumes=$(docker volume ls --filter "name=$CONTAINER_INITIALS" -q)
if [ -n "$volumes" ]; then
  docker volume rm $volumes || true
else
  echo "No project volumes to remove"
fi
