#!/usr/bin/env python3
"""
qBittorrent 慢速下载任务自动调整脚本
功能：定期检查 downloading 和 stalledDL 状态的任务，将速度低于阈值的移至队列末尾
条件：仅当存在 queuedDL 任务时才执行调整
认证：使用 qBittorrent WebUI API Key（qBittorrent ≥5.2.0），不再使用用户名/密码
日志：同时输出到控制台（docker logs）和文件（挂载卷 /app/logs/app.log）
"""

import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import schedule
import qbittorrentapi
from dotenv import load_dotenv

# 允许从任意工作目录运行（docker 中 cwd=/app，包在 /app/qbslowqueue）
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from qbslowqueue import __version__, __release_status__
except ImportError:  # 未以包形式安装时降级，避免崩溃
    __version__ = "unknown"
    __release_status__ = "unknown"

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
QB_API_KEY = os.getenv("QB_API_KEY", "")

# 速度阈值（字节/秒），默认 0 表示仅移动完全无速度的任务
SPEED_THRESHOLD = int(os.getenv("SPEED_THRESHOLD", 0))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))  # 秒

# ---------- 功能函数 ----------
def connect_qbittorrent():
    """连接 qBittorrent WebUI（使用 WebUI API Key 认证，qBittorrent ≥5.2.0）"""
    if not QB_API_KEY:
        raise ValueError(
            "未配置 QB_API_KEY。请在 .env / 环境变量中设置 qBittorrent WebUI 的 API Key"
            "（WebUI → 选项 → WebUI → 认证 → API Key）。"
        )
    client = qbittorrentapi.Client(
        host=QB_HOST,
        port=QB_PORT,
        api_key=QB_API_KEY,
    )
    try:
        # API Key 模式下跳过 cookie 登录，直接发起一次请求验证连通性与鉴权
        version = client.app.version
        logger.info(f"成功连接到 qBittorrent: {QB_HOST}:{QB_PORT}")
        logger.info(f"qBittorrent 版本: {version}")
        return client
    except qbittorrentapi.APIConnectionError as e:
        logger.error(f"qBittorrent 连接失败（请检查 QB_HOST/QB_PORT 是否可达）: {e}")
        raise
    except Exception as e:
        logger.error(f"qBittorrent 访问失败（请检查 QB_API_KEY 是否正确）: {e}")
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
    logger.info(f"qb-slow-queue v{__version__} ({__release_status__})")
    logger.info("🚀 qBittorrent 慢速任务调整服务启动")
    logger.info(f"速度阈值: {SPEED_THRESHOLD/1024:.0f} KB/s (0 表示仅移动无速度任务)")
    logger.info(f"检查间隔: {CHECK_INTERVAL} 秒")
    logger.info("仅处理状态为 'downloading' 或 'stalledDL' 的任务")
    logger.info("条件：仅当存在 'queuedDL' 任务时才执行调整")
    logger.info("认证方式：WebUI API Key（qBittorrent ≥5.2.0），不使用用户名/密码")
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
