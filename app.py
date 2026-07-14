#!/usr/bin/env python3
"""
qBittorrent 慢速下载任务自动调整脚本（仅处理 downloading 和 stalledDL 状态）
增加条件：仅当存在 queuedDL 任务时才执行移动
"""

import os
import time
import logging

import schedule
import qbittorrentapi
from dotenv import load_dotenv

load_dotenv()

# ---------- 配置 ----------
QB_HOST = os.getenv("QB_HOST", "192.168.1.100")
QB_PORT = int(os.getenv("QB_PORT", 8080))
QB_USER = os.getenv("QB_USER", "admin")
QB_PASS = os.getenv("QB_PASS", "adminadmin")

SPEED_THRESHOLD = int(os.getenv("SPEED_THRESHOLD", 0))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ---------- 日志 ----------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def connect_qbittorrent():
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
    return client.torrents_info()


def find_slow_torrents(torrents, threshold):
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
    logger.info("=" * 50)
    logger.info("开始扫描慢速下载任务...")

    try:
        client = connect_qbittorrent()
        all_torrents = get_all_torrents(client)

        if not all_torrents:
            logger.info("当前没有任何任务")
            return

        # 新增：没有排队任务则跳过调整
        if not has_queued_tasks(all_torrents):
            logger.info("⚠️ 当前没有 queuedDL 状态的任务，跳过慢速任务调整（无需改变顺序）")
            return

        slow = find_slow_torrents(all_torrents, SPEED_THRESHOLD)

        if not slow:
            logger.info(f"没有符合条件的慢速任务（阈值: {SPEED_THRESHOLD/1024:.0f} KB/s）")
            return

        move_torrents_to_bottom(client, slow)

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

    scan_and_adjust()

    schedule.every(CHECK_INTERVAL).seconds.do(scan_and_adjust)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()