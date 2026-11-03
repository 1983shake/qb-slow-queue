# 从 qbslowqueue/__init__.py 派生镜像 tag，并构建 + 启动服务。
# 版本唯一来源为 __init__.py，禁止在此处硬编码版本号。
$ErrorActionPreference = "Stop"

$tag = (python -c "import qbslowqueue; print(qbslowqueue.__docker_tag__)")
Write-Host "派生镜像 tag: $tag"

Write-Host "构建镜像..."
docker build -t $tag .

Write-Host "启动服务..."
$env:QB_IMAGE_TAG = $tag
docker compose up -d
Write-Host "完成。使用 'docker logs qb-slow-queue' 查看日志。"
