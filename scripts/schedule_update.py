#!/usr/bin/env python3
"""
安全知识库定时更新调度器
========================

功能：
  1. 每天凌晨 2:00 自动执行 fetch_nvd_cve.py 获取最新 CVE 数据
  2. 更新后自动调用后端 /api/reload 接口刷新知识库
  3. 支持日志记录

用法：
  python schedule_update.py              # 启动定时调度器（前台运行）
  python schedule_update.py --once       # 立即执行一次后退出（测试用）
  python schedule_update.py --interval 6 # 每 6 小时执行一次（代替默认的每天凌晨2点）
"""
import os
import sys
import time
import argparse
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import schedule
import requests

# ── 配置 ──────────────────────────────────────────────────
try:
    from backend.app.config import AUTO_UPDATE_ENABLED, HOST, PORT
except ImportError:
    AUTO_UPDATE_ENABLED = True
    HOST = "0.0.0.0"
    PORT = 8000

# 后端 API 地址（本机调用使用 localhost）
BACKEND_URL = f"http://localhost:{PORT}"
FETCH_SCRIPT = PROJECT_ROOT / "scripts" / "fetch_nvd_cve.py"

# 日志配置
LOG_DIR = PROJECT_ROOT / "backend" / "app" / "data"
LOG_FILE = LOG_DIR / "update_schedule.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_fetch_script(days: int = 7) -> bool:
    """
    运行 fetch_nvd_cve.py 脚本获取最新 CVE 数据

    Args:
        days: 获取最近几天的数据

    Returns:
        是否执行成功
    """
    logger.info(f"开始执行数据获取脚本 (最近 {days} 天)...")

    try:
        result = subprocess.run(
            [sys.executable, str(FETCH_SCRIPT), "--days", str(days)],
            capture_output=True,
            text=True,
            timeout=120,  # 2分钟超时
            cwd=str(PROJECT_ROOT),
        )

        # 记录输出
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                logger.info(f"[fetch_nvd_cve] {line}")

        if result.returncode == 0:
            logger.info("数据获取脚本执行成功")
            return True
        else:
            logger.error(f"数据获取脚本返回非零状态码: {result.returncode}")
            if result.stderr:
                logger.error(f"[stderr] {result.stderr[:500]}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("数据获取脚本执行超时 (>120秒)")
        return False
    except FileNotFoundError:
        logger.error(f"找不到 Python 解释器或脚本: {FETCH_SCRIPT}")
        return False
    except Exception as e:
        logger.error(f"运行数据获取脚本失败: {e}")
        return False


def call_reload_api() -> bool:
    """
    调用后端 /api/reload 接口刷新知识库

    Returns:
        是否调用成功
    """
    logger.info(f"调用后端 /api/reload 接口刷新知识库...")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/reload",
            json={},
            timeout=30,
        )
        data = response.json()

        if response.status_code == 200 and data.get("success"):
            logger.info(f"知识库刷新成功: {data.get('message', '')}")
            return True
        else:
            logger.warning(f"刷新接口返回异常: {data.get('message', '未知错误')}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接后端服务 ({BACKEND_URL})，请确认服务已启动")
        return False
    except requests.exceptions.Timeout:
        logger.error("调用 /api/reload 超时")
        return False
    except Exception as e:
        logger.error(f"调用刷新接口失败: {e}")
        return False


def scheduled_job():
    """定时任务：获取最新数据 → 刷新知识库"""
    logger.info("=" * 50)
    logger.info("定时更新任务触发")
    logger.info("=" * 50)

    # 步骤 1: 获取最新 CVE 数据
    fetch_ok = run_fetch_script(days=1)  # 每天更新只获取最近1天

    # 步骤 2: 刷新知识库
    if fetch_ok:
        call_reload_api()
    else:
        logger.warning("数据获取失败，跳过知识库刷新（保留现有数据）")

    logger.info("定时更新任务完成")


def main():
    parser = argparse.ArgumentParser(
        description="安全知识库定时更新调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python schedule_update.py              # 启动定时调度器（每天凌晨2点）
  python schedule_update.py --once       # 立即执行一次后退出
  python schedule_update.py --interval 6 # 每6小时执行一次
        """,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="立即执行一次更新后退出（用于测试）",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="每 N 小时执行一次（代替默认的每天凌晨2点）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="获取最近几天的数据（仅 --once 模式生效，默认 7）",
    )

    args = parser.parse_args()

    if not AUTO_UPDATE_ENABLED:
        logger.info("AUTO_UPDATE_ENABLED=False，定时更新已禁用")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── 一次性执行模式 ──
    if args.once:
        logger.info("一次性执行模式")
        if run_fetch_script(days=args.days):
            call_reload_api()
        logger.info("执行完毕，退出")
        return

    # ── 定时调度模式 ──
    if args.interval:
        # 每 N 小时执行
        schedule.every(args.interval).hours.do(scheduled_job)
        logger.info(f"定时调度已启动: 每 {args.interval} 小时执行一次")
    else:
        # 每天凌晨 2:00 执行
        schedule.every().day.at("02:00").do(scheduled_job)
        logger.info("定时调度已启动: 每天凌晨 02:00 执行")

    logger.info(f"后端地址: {BACKEND_URL}")
    logger.info(f"数据脚本: {FETCH_SCRIPT}")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("按 Ctrl+C 停止调度器")

    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # 每 30 秒检查一次
    except KeyboardInterrupt:
        logger.info("收到停止信号，调度器已停止")


if __name__ == "__main__":
    main()
