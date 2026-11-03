#!/usr/bin/env bash
# 从 qbslowqueue/__init__.py 派生镜像 tag，并构建 + 启动服务。
# 版本唯一来源为 __init__.py，禁止在此处硬编码版本号。
set -euo pipefail

cd "$(dirname "$0")"

TAG=$(python -c "import qbslowqueue; print(qbslowqueue.__docker_tag__)")
echo "派生镜像 tag: $TAG"

echo "构建镜像..."
docker build -t "$TAG" .

echo "启动服务（QB_IMAGE_TAG=$TAG）..."
QB_IMAGE_TAG="$TAG" docker compose up -d

echo "完成。使用 'docker logs qb-slow-queue' 查看日志。"
