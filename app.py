#!/usr/bin/env python3
"""
qBittorrent 慢速下载任务自动调整脚本
功能：每隔 CHECK_INTERVAL 秒检查 downloading 和 stalledDL 状态的任务，
      将当前下载速度低于阈值的任务移至队列末尾
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
# 检查间隔（秒）：每隔多久扫描一次，并对本次低于阈值的任务执行移动。
# 已合并原 SLOW_DURATION：不再做"持续观察窗口"判定，每次扫描即时移动。
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))

# ---------- 功能函数 ----------
def connect_qbittorrent():
    """创建 qBittorrent WebUI Client（WebUI API Key 认证，qBittorrent ≥5.2.0）。

    仅校验 API Key 已配置；真正的连通性由首次 torrents_info 调用确认，
    避免每次扫描都额外发起一次探活请求，降低对 qBittorrent 的请求压力。
    """
    if not QB_API_KEY:
        raise ValueError(
            "未配置 QB_API_KEY。请在 .env / 环境变量中设置 qBittorrent WebUI 的 API Key"
            "（WebUI → 选项 → WebUI → 认证 → API Key）。"
        )
    return qbittorrentapi.Client(
        host=QB_HOST,
        port=QB_PORT,
        api_key=QB_API_KEY,
    )


def get_all_torrents(client):
    """获取所有任务（单次请求，供本次扫描复用，避免重复拉取）"""
    return client.torrents_info()


def find_slow_torrents(torrents, threshold):
    """返回所有 downloading/stalledDL 且当前下载速度低于阈值的任务。

    合并 CHECK_INTERVAL 与 SLOW_DURATION 后，不再做"持续观察窗口"判定：
    每次检查只要任务当前速度低于阈值即视为慢速并移动，简单直观、低开销。
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


def scan_and_adjust(client):
    """主扫描和调整函数（复用同一个 client，不在每次扫描重建连接）"""
    logger.info("=" * 50)
    logger.info("开始扫描慢速下载任务...")

    try:
        all_torrents = get_all_torrents(client)
    except Exception as e:
        logger.error(f"获取任务列表失败（请检查连通性 / API Key 是否正确）: {e}")
        return

    if not all_torrents:
        logger.info("当前没有任何任务")
        return

    # 仅当存在 queuedDL 任务时才执行调整
    if not has_queued_tasks(all_torrents):
        logger.info("⚠️ 当前没有 queuedDL 状态的任务，跳过慢速任务调整（无需改变顺序）")
        return

    slow = find_slow_torrents(all_torrents, SPEED_THRESHOLD)

    if not slow:
        logger.info(f"没有低于阈值（{SPEED_THRESHOLD/1024:.0f} KB/s）的下载任务")
        return

    move_torrents_to_bottom(client, slow)

    # 直接用本次已获取的任务列表统计，避免再次请求 torrents_info
    downloading_count = len([t for t in all_torrents if t.state in ("downloading", "stalledDL")])
    logger.info(f"调整后，当前下载/停滞状态任务数: {downloading_count}")


def main():
    logger.info(f"qb-slow-queue v{__version__} ({__release_status__})")
    logger.info("🚀 qBittorrent 慢速任务调整服务启动")
    logger.info(f"速度阈值: {SPEED_THRESHOLD/1024:.0f} KB/s (0 表示仅移动无速度任务)")
    logger.info(f"检查间隔: {CHECK_INTERVAL} 秒（每次检查即对低于阈值的任务移动）")
    logger.info("仅处理状态为 'downloading' 或 'stalledDL' 的任务")
    logger.info("条件：仅当存在 'queuedDL' 任务时才执行调整")
    logger.info("认证方式：WebUI API Key（qBittorrent ≥5.2.0），不使用用户名/密码")
    logger.info(f"日志文件: {LOG_FILE}")

    # 创建一次 Client 并复用，降低连接与探活开销
    try:
        client = connect_qbittorrent()
    except Exception as e:
        logger.error(f"初始化 qBittorrent 连接失败: {e}", exc_info=True)
        sys.exit(1)

    # 启动时一次性确认连通性（仅此一次网络探活）
    try:
        version = client.app.version
        logger.info(f"成功连接到 qBittorrent: {QB_HOST}:{QB_PORT}")
        logger.info(f"qBittorrent 版本: {version}")
    except Exception as e:
        logger.warning(f"⚠️ 启动连通性校验失败，将在后续扫描中重试: {e}")

    # 启动时立即执行一次
    scan_and_adjust(client)

    # 主循环：使用简单 sleep 轮询，避免引入调度库的额外开销
    logger.info(f"进入定时循环，每 {CHECK_INTERVAL} 秒扫描一次...")
    while True:
        time.sleep(CHECK_INTERVAL)
        scan_and_adjust(client)


if __name__ == "__main__":
    main()
