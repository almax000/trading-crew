"""
TradingCrew Web UI - FastAPI 后端

提供 REST API 供前端调用，支持热重载开发。

启动方式:
    uvicorn gui.server:app --reload --port 1788
"""

import os
import asyncio
import json
from typing import List, Optional, Dict, Set
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import (
    INVITE_CODES,
    MARKET_OPTIONS,
    ANALYST_OPTIONS,
    AGENT_DISPLAY_NAMES,
    AGENT_ORDER,
    get_date_presets,
    get_default_dates,
    is_admin,
)
from .auth import authenticate as auth_check
from .ticker_validator import validate_ticker_format, validate_and_get_name
from .session_manager import (
    get_session_manager,
    Session,
    SessionStatus,
    set_sse_publisher,
)


# ============ Pydantic Models ============

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None


class TickerValidateRequest(BaseModel):
    ticker: str
    market: str


class TickerValidateResponse(BaseModel):
    valid: bool
    normalized: str
    name: str
    error: str


class CreateSessionRequest(BaseModel):
    ticker: str
    market: str
    start_date: str
    end_date: str
    analysts: List[str] = ["market", "social", "news", "fundamentals"]


class SessionResponse(BaseModel):
    id: str
    ticker: str
    stock_name: str
    market: str
    start_date: str
    end_date: str
    user_id: str = ""
    status: str
    decision: str
    progress: List[str]
    reports: dict
    created_at: str
    error_msg: str
    current_agent: str


class ConfigResponse(BaseModel):
    markets: dict
    analysts: dict
    agent_names: dict
    agent_order: List[str]
    date_presets: List[dict]
    default_dates: dict
    is_admin: bool = False


class UserContext(BaseModel):
    """用户上下文"""
    username: str = ""
    is_admin: bool = False


def get_current_user(x_username: Optional[str] = Header(None)) -> UserContext:
    """从请求头获取当前用户"""
    if not x_username:
        return UserContext()
    return UserContext(
        username=x_username,
        is_admin=is_admin(x_username),
    )


def session_to_response(s: Session) -> SessionResponse:
    """将 Session 转换为 SessionResponse"""
    return SessionResponse(
        id=s.id,
        ticker=s.ticker,
        stock_name=s.stock_name,
        market=s.market,
        start_date=s.start_date,
        end_date=s.end_date,
        user_id=s.user_id,
        status=s.status.value,
        decision=s.decision,
        progress=s.progress,
        reports=s.reports,
        created_at=s.created_at,
        error_msg=s.error_msg,
        current_agent=s.current_agent,
    )


# ============ SSE Manager ============

class SSEManager:
    """管理 SSE 连接"""

    def __init__(self):
        # session_id -> Set[asyncio.Queue]
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """订阅 session 更新"""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = set()
            self._subscribers[session_id].add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """取消订阅"""
        async with self._lock:
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(queue)
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]

    async def publish(self, session_id: str, data: dict):
        """发布更新到所有订阅者"""
        async with self._lock:
            subscribers = self._subscribers.get(session_id, set()).copy()
        for queue in subscribers:
            try:
                await queue.put(data)
            except Exception:
                pass

    def publish_sync(self, session_id: str, data: dict):
        """同步版本的 publish（供 session_manager 调用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.publish(session_id, data), loop)
            else:
                loop.run_until_complete(self.publish(session_id, data))
        except RuntimeError:
            # 没有运行的事件循环，创建新的
            asyncio.run(self.publish(session_id, data))


# 全局 SSE 管理器
sse_manager = SSEManager()


# ============ FastAPI App ============

app = FastAPI(
    title="TradingCrew API",
    description="多 Agent 协作的 AI 交易分析系统",
    version="1.0.0",
)

# CORS 配置（开发环境允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    # 设置 SSE 发布器
    set_sse_publisher(sse_manager.publish_sync)

# 静态文件目录
STATIC_DIR = Path(__file__).parent / "static"


# ============ API Routes ============

@app.get("/api/config")
async def get_config(user: UserContext = Depends(get_current_user)) -> ConfigResponse:
    """获取前端配置"""
    start, end = get_default_dates()
    return ConfigResponse(
        markets=MARKET_OPTIONS,
        analysts=ANALYST_OPTIONS,
        agent_names=AGENT_DISPLAY_NAMES,
        agent_order=AGENT_ORDER,
        date_presets=get_date_presets(),
        default_dates={"start": start, "end": end},
        is_admin=user.is_admin,
    )


@app.post("/api/auth/login")
async def login(req: LoginRequest) -> LoginResponse:
    """用户登录"""
    success, message = auth_check(req.username, req.password)
    return LoginResponse(
        success=success,
        message=message,
        username=req.username if success else None,
    )


@app.post("/api/auth/logout")
async def logout() -> dict:
    """用户登出"""
    return {"success": True}


@app.post("/api/ticker/validate")
async def validate_ticker(req: TickerValidateRequest) -> TickerValidateResponse:
    """验证股票代码"""
    market = MARKET_OPTIONS.get(req.market, req.market)

    # 先做格式验证
    is_valid, normalized, error = validate_ticker_format(req.ticker, market)

    if not is_valid:
        return TickerValidateResponse(
            valid=False,
            normalized="",
            name="",
            error=error,
        )

    # 尝试获取名称
    try:
        success, normalized, name = validate_and_get_name(req.ticker, market)
        if success:
            return TickerValidateResponse(
                valid=True,
                normalized=normalized,
                name=name,
                error="",
            )
        else:
            return TickerValidateResponse(
                valid=False,
                normalized="",
                name="",
                error=name,  # name contains error message
            )
    except Exception as e:
        # 名称查询失败，但格式正确
        return TickerValidateResponse(
            valid=True,
            normalized=normalized,
            name="",
            error="",
        )


@app.get("/api/sessions")
async def list_sessions(user: UserContext = Depends(get_current_user)) -> List[SessionResponse]:
    """获取当前用户的 Session 列表（管理员可见所有）"""
    manager = get_session_manager()
    sessions = manager.get_all_sessions(
        user_id=user.username,
        is_admin=user.is_admin,
    )
    return [session_to_response(s) for s in sessions]


@app.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: UserContext = Depends(get_current_user),
) -> SessionResponse:
    """获取单个 Session 详情"""
    manager = get_session_manager()
    session = manager.get_session(
        session_id,
        user_id=user.username,
        is_admin=user.is_admin,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_to_response(session)


@app.post("/api/sessions")
async def create_session(
    req: CreateSessionRequest,
    user: UserContext = Depends(get_current_user),
) -> SessionResponse:
    """创建并启动新 Session"""
    market = MARKET_OPTIONS.get(req.market, req.market)

    # 验证股票
    is_valid, normalized, name_or_error = validate_and_get_name(req.ticker, market)
    if not is_valid:
        raise HTTPException(status_code=400, detail=name_or_error)

    # 创建 Session（关联当前用户）
    manager = get_session_manager()
    session = manager.create_session(
        ticker=normalized,
        stock_name=name_or_error if is_valid else "",
        market=market,
        start_date=req.start_date,
        end_date=req.end_date,
        user_id=user.username,
    )

    # 启动 Session
    manager.start_session(session.id, req.analysts)

    return session_to_response(session)


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: UserContext = Depends(get_current_user),
) -> dict:
    """删除 Session（只能删除自己的，管理员可删除所有）"""
    manager = get_session_manager()

    # 先检查权限
    session = manager.get_session(session_id, user.username, user.is_admin)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


@app.post("/api/sessions/{session_id}/retry")
async def retry_session(
    session_id: str,
    user: UserContext = Depends(get_current_user),
) -> SessionResponse:
    """重试失败的 Session（只能重试自己的，管理员可重试所有）"""
    manager = get_session_manager()
    session = manager.get_session(session_id, user.username, user.is_admin)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != SessionStatus.ERROR:
        raise HTTPException(status_code=400, detail="只能重试出错的会话")

    # 重置 Session 状态并重新启动
    manager.retry_session(session_id)

    # 重新获取 Session
    session = manager.get_session(session_id, user.username, user.is_admin)

    return session_to_response(session)


@app.get("/api/sessions/running/count")
async def get_running_count(user: UserContext = Depends(get_current_user)) -> dict:
    """获取运行中的 Session 数量（当前用户的，管理员可见所有）"""
    manager = get_session_manager()
    return {
        "count": manager.get_running_count(
            user_id=user.username,
            is_admin=user.is_admin,
        )
    }


# ============ SSE Endpoint ============

@app.get("/api/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    username: Optional[str] = None,  # EventSource 不支持 header，用 query param
):
    """SSE 端点：实时推送 Session 状态更新"""
    # 从 query param 获取用户信息
    user_is_admin = is_admin(username) if username else False

    manager = get_session_manager()
    session = manager.get_session(session_id, username, user_is_admin)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        queue = await sse_manager.subscribe(session_id)
        try:
            # 发送初始状态
            initial_data = session_to_response(
                manager.get_session(session_id, username, user_is_admin)
            )
            yield f"data: {json.dumps(initial_data.model_dump())}\n\n"

            # 如果已完成或出错，发送完毕后关闭
            if session.status in (SessionStatus.COMPLETED, SessionStatus.ERROR):
                return

            # 监听更新
            while True:
                try:
                    # 30 秒超时，发送心跳
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"

                    # 如果状态变为完成或出错，结束流
                    if data.get("status") in ("completed", "error"):
                        break
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield ": heartbeat\n\n"
        finally:
            await sse_manager.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


# ============ Static Files ============

# 挂载静态文件目录
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """返回前端页面"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "TradingCrew API", "docs": "/docs"}


@app.get("/favicon.ico")
async def favicon():
    """Favicon"""
    favicon_file = STATIC_DIR / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(favicon_file)
    raise HTTPException(status_code=404)


# ============ 启动入口 ============

def run_server(host: str = "0.0.0.0", port: int = 1788, reload: bool = False):
    """启动服务器"""
    import uvicorn

    print(f"\nTradingCrew Web UI 启动中...")
    print(f"地址: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")
    print(f"热重载: {'开启' if reload else '关闭'}")
    print()

    uvicorn.run(
        "gui.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server(reload=True)
