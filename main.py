#!/usr/bin/env python3
"""
股票分析平台主入口
启动 FastAPI 服务和定时更新调度器
"""

import argparse
import sys
from pathlib import Path

import uvicorn

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api import app  # noqa: E402,F401


def main():
    parser = argparse.ArgumentParser(description="股票分析平台")
    parser.add_argument("--host", default="0.0.0.0", help="服务主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--reload", action="store_true", help="开发模式自动重载")

    args = parser.parse_args()

    print(f"""
股票分析平台启动中...
API 文档: http://{args.host}:{args.port}/docs
前端界面: http://{args.host}:{args.port}/app
    """)

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
