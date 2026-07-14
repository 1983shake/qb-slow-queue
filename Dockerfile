FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制脚本
COPY app.py .

# 创建非 root 用户运行（提升安全性）
RUN useradd -m -u 1000 qbuser && chown -R qbuser:qbuser /app
USER qbuser

# 容器启动命令
CMD ["python", "-u", "app.py"]