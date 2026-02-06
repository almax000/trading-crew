#!/usr/bin/env python3
"""
TradingCrew Web UI 启动脚本

用法:
    python run_gui.py                    # 默认启动
    python run_gui.py --port 8080        # 指定端口
"""

import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_env():
    """加载 .env 文件"""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        print(f"加载环境变量: {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # 移除引号
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    if value:
                        os.environ[key] = value


def main():
    # 加载 .env 文件
    load_env()

    # 检查环境变量
    if not os.environ.get("DASHSCOPE_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("警告: 未检测到 API Key")
        print("请设置 DASHSCOPE_API_KEY (中国用户) 或 OPENROUTER_API_KEY (国际用户)")
        print("参考 .env.example 配置环境变量")
        print()

    # 获取端口 (Railway 使用 PORT 环境变量)
    port = int(os.environ.get("PORT", os.environ.get("WEB_PORT", 1788)))
    host = "0.0.0.0"

    from gui.server import run_server
    run_server(host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
