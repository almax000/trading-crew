# TradingCrew Web UI - Bun + Python 混合镜像
#
# 构建:
#   docker build -f Dockerfile.bun -t tradingcrew-bun .
#
# 运行:
#   docker run -p 1788:1788 --env-file .env tradingcrew-bun

# ============ Stage 1: Python 依赖 ============
FROM python:3.11-slim AS python-deps

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============ Stage 2: Python 3.11 + Bun 运行环境 ============
FROM python:3.11-slim

WORKDIR /app

# 安装 Bun 和必要工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && curl -fsSL https://bun.sh/install | bash \
    && rm -rf /var/lib/apt/lists/*

# 将 Bun 添加到 PATH
ENV PATH="/root/.bun/bin:$PATH"

# 从 Python 构建阶段复制已安装的包
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# 设置 Python 路径
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:/app

# ============ 复制项目代码 ============

# Python 分析服务
COPY analysis_service ./analysis_service

# TradingCrew 核心
COPY tradingcrew ./tradingcrew

# Bun Web 项目
COPY web/package.json web/bun.lockb* ./web/
WORKDIR /app/web
RUN bun install --frozen-lockfile 2>/dev/null || bun install

# 复制 Web 源代码
COPY web/src ./src
COPY web/static ./static
COPY web/tsconfig.json .

WORKDIR /app

# 复制启动脚本
COPY start.sh .
RUN chmod +x start.sh

# ============ 环境变量 ============
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NODE_ENV=production

# ============ 端口 ============
EXPOSE 1788

# ============ 健康检查 ============
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:1788/health || exit 1

# ============ 启动 ============
CMD ["./start.sh"]
