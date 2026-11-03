FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
# 构建环境可能无法直连 pypi.org（如 CNB / 受限网络），改用国内镜像拉取依赖。
# 如所用构建网络对这两个镜像也不可达，请将下方地址替换为可用镜像（如阿里云/华为云 PyPI 镜像）。
COPY requirements.txt .
RUN printf '%s\n' \
        '[global]' \
        'index-url = https://mirrors.cloud.tencent.com/pypi/simple' \
        'extra-index-url = https://pypi.tuna.tsinghua.edu.cn/simple' \
        'trusted-host = mirrors.cloud.tencent.com pypi.tuna.tsinghua.edu.cn' \
    > /etc/pip.conf && \
    pip install --no-cache-dir -r requirements.txt

# 复制脚本与版本包
COPY app.py .
COPY qbslowqueue ./qbslowqueue

# 创建非 root 用户运行（提升安全性）
RUN useradd -m -u 1000 qbuser && chown -R qbuser:qbuser /app
USER qbuser

# 容器启动命令
# 镜像 tag 由 qbslowqueue/__init__.py 的 __docker_tag__ 派生（见 build.sh / build.ps1）
CMD ["python", "-u", "app.py"]
