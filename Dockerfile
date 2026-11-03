FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖（容错源链：先原链接 pypi.org，失败再退回国内镜像）
# 构建环境可能无法直连 pypi.org（如 CNB / 受限网络）。
# 策略：默认源优先，失败后依次尝试腾讯云、清华、阿里云镜像，任一成功即停。
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 2 --timeout 30 -r requirements.txt \
    || pip install --no-cache-dir --retries 2 --timeout 30 -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple \
    || pip install --no-cache-dir --retries 2 --timeout 30 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    || pip install --no-cache-dir --retries 2 --timeout 30 -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# 复制脚本与版本包
COPY app.py .
COPY qbslowqueue ./qbslowqueue

# 创建非 root 用户运行（提升安全性）
RUN useradd -m -u 1000 qbuser && chown -R qbuser:qbuser /app
USER qbuser

# 容器启动命令
# 镜像 tag 由 qbslowqueue/__init__.py 的 __docker_tag__ 派生（见 build.sh / build.ps1）
CMD ["python", "-u", "app.py"]
