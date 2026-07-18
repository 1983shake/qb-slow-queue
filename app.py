#!/usr/bin/env python3
"""
qBittorrent 慢速下载任务自动调整脚本
功能：定期检查 downloading 和 stalledDL 状态的任务，将速度低于阈值的移至队列末尾
条件：仅当存在 queuedDL 任务时才执行调整
日志：同时输出到控制台（docker logs）和文件（挂载卷 /app/logs/app.log）
"""

import os
import time
import logging
from logging.handlers import RotatingFileHandler

import schedule
import qbittorrentapi
from dotenv import load_dotenv

# ---------- 加载 .env ----------
load_dotenv()

# ---------- 日志配置 ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = "/app/logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# 确保日志目录存在（容器启动时创建）
os.makedirs(LOG_DIR, exist_ok=True)

# 配置根日志器
logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL))

# 清除已有的 handlers（避免重复）
if logger.hasHandlers():
    logger.handlers.clear()

# 1. 控制台 Handler（输出到 stdout，供 docker logs 查看）
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL))
console_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# 2. 文件 Handler（轮转日志，写入挂载卷）
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(getattr(logging, LOG_LEVEL))
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# ---------- 配置参数 ----------
QB_HOST = os.getenv("QB_HOST", "192.168.1.100")
QB_PORT = int(os.getenv("QB_PORT", 8080))
QB_USER = os.getenv("QB_USER", "admin")
QB_PASS = os.getenv("QB_PASS", "adminadmin")

# 速度阈值（字节/秒），默认 0 表示仅移动完全无速度的任务
SPEED_THRESHOLD = int(os.getenv("SPEED_THRESHOLD", 0))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))  # 秒

# ---------- 功能函数 ----------
def connect_qbittorrent():
    """连接 qBittorrent WebUI"""
    client = qbittorrentapi.Client(
        host=QB_HOST,
        port=QB_PORT,
        username=QB_USER,
        password=QB_PASS,
    )
    try:
        client.auth_log_in()
        logger.info(f"成功连接到 qBittorrent: {QB_HOST}:{QB_PORT}")
        logger.info(f"qBittorrent 版本: {client.app.version}")
        return client
    except qbittorrentapi.LoginFailed as e:
        logger.error(f"qBittorrent 登录失败: {e}")
        raise


def get_all_torrents(client):
    """获取所有任务"""
    return client.torrents_info()


def find_slow_torrents(torrents, threshold):
    """
    筛选出状态为 'downloading' 或 'stalledDL'，且下载速度低于阈值的任务
    """
    slow = []
    for t in torrents:
        if t.state not in ("downloading", "stalledDL"):
            continue
        speed = t.dlspeed
        if speed < threshold:
            slow.append({
                "hash": t.hash,
                "name": t.name,
                "state": t.state,
                "speed": speed,
                "speed_kb": round(speed / 1024, 1),
            })
    return slow


def move_torrents_to_bottom(client, slow_torrents):
    """将慢速任务移至队列末尾（使用 torrents_bottom_priority）"""
    if not slow_torrents:
        return

    hashes = [t["hash"] for t in slow_torrents]
    logger.info(f"准备将 {len(hashes)} 个慢速任务移至队列末尾:")
    for t in slow_torrents:
        logger.info(f"  - {t['name']} [{t['state']}] ({t['speed_kb']} KB/s)")

    try:
        client.torrents_bottom_priority(torrent_hashes=hashes)
        logger.info(f"✅ 已成功将 {len(hashes)} 个任务移至队列末尾")
    except Exception as e:
        logger.error(f"调整队列位置失败: {e}")


def has_queued_tasks(torrents):
    """检查是否存在排队等待下载的任务（状态为 queuedDL）"""
    for t in torrents:
        if t.state == "queuedDL":
            return True
    return False


def scan_and_adjust():
    """主扫描和调整函数"""
    logger.info("=" * 50)
    logger.info("开始扫描慢速下载任务...")

    try:
        client = connect_qbittorrent()
        all_torrents = get_all_torrents(client)

        if not all_torrents:
            logger.info("当前没有任何任务")
            return

        # 仅当存在 queuedDL 任务时才执行调整
        if not has_queued_tasks(all_torrents):
            logger.info("⚠️ 当前没有 queuedDL 状态的任务，跳过慢速任务调整（无需改变顺序）")
            return

        slow = find_slow_torrents(all_torrents, SPEED_THRESHOLD)

        if not slow:
            logger.info(f"没有符合条件的慢速任务（阈值: {SPEED_THRESHOLD/1024:.0f} KB/s）")
            return

        move_torrents_to_bottom(client, slow)

        # 输出调整后的摘要信息
        remaining = client.torrents_info()
        downloading_count = len([t for t in remaining if t.state in ("downloading", "stalledDL")])
        logger.info(f"调整后，当前下载/停滞状态任务数: {downloading_count}")

    except Exception as e:
        logger.error(f"扫描过程发生异常: {e}", exc_info=True)


def main():
    logger.info("🚀 qBittorrent 慢速任务调整服务启动")
    logger.info(f"速度阈值: {SPEED_THRESHOLD/1024:.0f} KB/s (0 表示仅移动无速度任务)")
    logger.info(f"检查间隔: {CHECK_INTERVAL} 秒")
    logger.info("仅处理状态为 'downloading' 或 'stalledDL' 的任务")
    logger.info("条件：仅当存在 'queuedDL' 任务时才执行调整")
    logger.info(f"日志文件: {LOG_FILE}")

    # 启动时立即执行一次
    scan_and_adjust()

    # 定时任务
    schedule.every(CHECK_INTERVAL).seconds.do(scan_and_adjust)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()