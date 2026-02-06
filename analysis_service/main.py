"""
TradingCrew Analysis Service - FastAPI 入口

提供 NDJSON 流式分析 API，供 Node.js Web 后端调用。

启动方式:
    cd /path/to/trading-crew
    python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000
"""

import json
import sys
import os
import asyncio
import threading
import queue
from typing import List

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


app = FastAPI(
    title="TradingCrew Analysis Service",
    description="内部分析服务，提供 NDJSON 流式输出",
    version="1.0.0",
)


class AnalyzeRequest(BaseModel):
    """分析请求参数"""
    ticker: str
    date: str
    market: str = "A-share"
    analysts: List[str] = ["market", "social", "news", "fundamentals"]
    model: str = "deepseek-v3"  # 可选: deepseek-v3, qwen3-max, gpt-4o, claude-sonnet-4


def run_analysis_in_thread(
    result_queue: queue.Queue,
    ticker: str,
    date: str,
    market: str,
    analysts: List[str],
    model: str,
):
    """在单独线程中运行分析，结果放入队列"""
    try:
        from .service import AnalysisService
        service = AnalysisService()

        for agent_name, content in service.analyze_stream(
            ticker=ticker,
            date=date,
            market=market,
            selected_analysts=analysts,
            model=model,
        ):
            result_queue.put(("data", agent_name, content))

        # 标记完成
        result_queue.put(("done", None, None))
    except Exception as e:
        result_queue.put(("error", str(e), None))


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    流式分析股票

    返回 NDJSON 格式:
    {"agent": "__HEARTBEAT__", "content": ""}  # 保活心跳
    {"agent": "Market Analyst", "content": "..."}
    {"agent": "Social Analyst", "content": "..."}
    ...
    {"agent": "__FINAL__", "content": "BUY"}
    """

    async def generate():
        # 创建结果队列
        result_queue = queue.Queue()

        # 在后台线程启动分析
        thread = threading.Thread(
            target=run_analysis_in_thread,
            args=(result_queue, req.ticker, req.date, req.market, req.analysts, req.model),
            daemon=True,
        )
        thread.start()

        # 发送初始心跳
        yield json.dumps({
            "agent": "__HEARTBEAT__",
            "content": "Analysis started",
        }, ensure_ascii=False) + "\n"

        heartbeat_interval = 15  # 每 15 秒发送心跳
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            try:
                # 非阻塞获取结果，超时 1 秒
                try:
                    msg_type, agent_name, content = result_queue.get(timeout=1.0)

                    if msg_type == "done":
                        break
                    elif msg_type == "error":
                        yield json.dumps({
                            "agent": "__ERROR__",
                            "content": agent_name,  # 错误信息在 agent_name 位置
                        }, ensure_ascii=False) + "\n"
                        break
                    elif msg_type == "data":
                        yield json.dumps({
                            "agent": agent_name,
                            "content": content,
                        }, ensure_ascii=False) + "\n"
                        last_heartbeat = asyncio.get_event_loop().time()

                except queue.Empty:
                    # 队列为空，检查是否需要发送心跳
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield json.dumps({
                            "agent": "__HEARTBEAT__",
                            "content": "",
                        }, ensure_ascii=False) + "\n"
                        last_heartbeat = current_time

                    # 让出控制权
                    await asyncio.sleep(0.1)

            except Exception as e:
                yield json.dumps({
                    "agent": "__ERROR__",
                    "content": str(e),
                }, ensure_ascii=False) + "\n"
                break

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@app.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    """
    Token-level streaming analysis (新端点)

    返回 NDJSON 格式:
    {"type": "node_start", "agent": "Market Analyst", "content": null}
    {"type": "token", "agent": "Market Analyst", "content": "分"}
    {"type": "token", "agent": "Market Analyst", "content": "析"}
    {"type": "node_end", "agent": "Market Analyst", "content": "...完整内容..."}
    {"type": "heartbeat", "agent": null, "content": null}  # 每15秒
    {"type": "complete", "agent": null, "content": "BUY"}
    {"type": "error", "agent": null, "content": "错误信息"}
    """
    from .service import AnalysisService

    async def generate():
        service = AnalysisService()

        # 发送初始心跳
        yield json.dumps({
            "type": "heartbeat",
            "agent": None,
            "content": "Analysis started",
        }, ensure_ascii=False) + "\n"

        heartbeat_interval = 15
        last_heartbeat = asyncio.get_event_loop().time()

        try:
            async for event_type, agent_name, content in service.analyze_stream_tokens(
                ticker=req.ticker,
                date=req.date,
                market=req.market,
                selected_analysts=req.analysts,
                model=req.model,
            ):
                # 发送事件
                yield json.dumps({
                    "type": event_type,
                    "agent": agent_name,
                    "content": content,
                }, ensure_ascii=False) + "\n"

                # 更新心跳时间
                last_heartbeat = asyncio.get_event_loop().time()

                # 完成或错误时退出
                if event_type in ("complete", "error", "quota_error", "timeout_error"):
                    break

                # 检查是否需要发送心跳
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    yield json.dumps({
                        "type": "heartbeat",
                        "agent": None,
                        "content": None,
                    }, ensure_ascii=False) + "\n"
                    last_heartbeat = current_time

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "agent": None,
                "content": str(e),
            }, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "ok", "service": "analysis"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
