"""
TradingCrew Analysis Service - FastAPI entry point

Provides NDJSON streaming analysis API, called by the Node.js Web backend.

Start:
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

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


app = FastAPI(
    title="TradingCrew Analysis Service",
    description="Internal analysis service providing NDJSON streaming output",
    version="1.0.0",
)


class AnalyzeRequest(BaseModel):
    """Analysis request parameters"""
    ticker: str
    date: str
    market: str = "A-share"
    analysts: List[str] = ["market", "social", "news", "fundamentals"]
    model: str = "deepseek-v3"  # Options: deepseek-v3, qwen3-max, gpt-4o, claude-sonnet-4


def run_analysis_in_thread(
    result_queue: queue.Queue,
    ticker: str,
    date: str,
    market: str,
    analysts: List[str],
    model: str,
):
    """Run analysis in a separate thread, putting results into the queue"""
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

        # Mark completion
        result_queue.put(("done", None, None))
    except Exception as e:
        result_queue.put(("error", str(e), None))


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Streaming stock analysis

    Returns NDJSON format:
    {"agent": "__HEARTBEAT__", "content": ""}  # Keep-alive heartbeat
    {"agent": "Market Analyst", "content": "..."}
    {"agent": "Social Analyst", "content": "..."}
    ...
    {"agent": "__FINAL__", "content": "BUY"}
    """

    async def generate():
        # Create result queue
        result_queue = queue.Queue()

        # Start analysis in background thread
        thread = threading.Thread(
            target=run_analysis_in_thread,
            args=(result_queue, req.ticker, req.date, req.market, req.analysts, req.model),
            daemon=True,
        )
        thread.start()

        # Send initial heartbeat
        yield json.dumps({
            "agent": "__HEARTBEAT__",
            "content": "Analysis started",
        }, ensure_ascii=False) + "\n"

        heartbeat_interval = 15  # Send heartbeat every 15 seconds
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            try:
                # Non-blocking get with 1 second timeout
                try:
                    msg_type, agent_name, content = result_queue.get(timeout=1.0)

                    if msg_type == "done":
                        break
                    elif msg_type == "error":
                        yield json.dumps({
                            "agent": "__ERROR__",
                            "content": agent_name,  # Error message is in agent_name field
                        }, ensure_ascii=False) + "\n"
                        break
                    elif msg_type == "data":
                        yield json.dumps({
                            "agent": agent_name,
                            "content": content,
                        }, ensure_ascii=False) + "\n"
                        last_heartbeat = asyncio.get_event_loop().time()

                except queue.Empty:
                    # Queue empty, check if heartbeat needed
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield json.dumps({
                            "agent": "__HEARTBEAT__",
                            "content": "",
                        }, ensure_ascii=False) + "\n"
                        last_heartbeat = current_time

                    # Yield control
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
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    """
    Token-level streaming analysis (new endpoint)

    Returns NDJSON format:
    {"type": "node_start", "agent": "Market Analyst", "content": null}
    {"type": "token", "agent": "Market Analyst", "content": "The"}
    {"type": "token", "agent": "Market Analyst", "content": " analysis"}
    {"type": "node_end", "agent": "Market Analyst", "content": "...full content..."}
    {"type": "heartbeat", "agent": null, "content": null}  # Every 15 seconds
    {"type": "complete", "agent": null, "content": "BUY"}
    {"type": "error", "agent": null, "content": "Error message"}
    """
    from .service import AnalysisService

    async def generate():
        service = AnalysisService()

        # Send initial heartbeat
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
                # Send event
                yield json.dumps({
                    "type": event_type,
                    "agent": agent_name,
                    "content": content,
                }, ensure_ascii=False) + "\n"

                # Update heartbeat time
                last_heartbeat = asyncio.get_event_loop().time()

                # Exit on completion or error
                if event_type in ("complete", "error", "quota_error", "timeout_error"):
                    break

                # Check if heartbeat needed
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
    """Health check endpoint"""
    return {"status": "ok", "service": "analysis"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
