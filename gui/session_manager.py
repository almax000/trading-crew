"""
Session 管理模块

管理分析 Session 的创建、执行、状态跟踪。
支持并发执行多个 Session，数据持久化到 JSON 文件。
"""

import json
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

from .config import AGENT_ORDER

# SSE 发布器（由 server.py 设置，避免循环导入）
_sse_publisher = None


def set_sse_publisher(publisher):
    """设置 SSE 发布器（由 server.py 调用）"""
    global _sse_publisher
    _sse_publisher = publisher


# Session 存储文件路径
# Railway Volume 挂载到 /data，本地开发用项目目录
import os
_data_dir = os.environ.get("DATA_DIR", str(Path(__file__).parent.parent / "data"))
SESSIONS_FILE = Path(_data_dir) / "sessions.json"


class SessionStatus(Enum):
    """Session 状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Session:
    """Session 数据结构"""
    id: str
    ticker: str
    stock_name: str
    market: str
    start_date: str
    end_date: str
    user_id: str = ""  # 所属用户
    status: SessionStatus = SessionStatus.PENDING
    decision: str = ""
    progress: List[str] = field(default_factory=list)
    reports: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    error_msg: str = ""
    current_agent: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "market": self.market,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "user_id": self.user_id,
            "status": self.status.value,
            "decision": self.decision,
            "progress": self.progress,
            "reports": self.reports,
            "created_at": self.created_at,
            "error_msg": self.error_msg,
            "current_agent": self.current_agent,
        }

    @staticmethod
    def from_dict(data: dict) -> "Session":
        """从字典创建 Session"""
        return Session(
            id=data.get("id", str(uuid.uuid4())),
            ticker=data.get("ticker", ""),
            stock_name=data.get("stock_name", ""),
            market=data.get("market", "A-share"),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            user_id=data.get("user_id", ""),
            status=SessionStatus(data.get("status", "pending")),
            decision=data.get("decision", ""),
            progress=data.get("progress", []),
            reports=data.get("reports", {}),
            created_at=data.get("created_at", ""),
            error_msg=data.get("error_msg", ""),
            current_agent=data.get("current_agent", ""),
        )


class SessionManager:
    """
    Session 管理器

    负责 Session 的生命周期管理和并发执行。
    """

    def __init__(self, max_workers: int = 3):
        """
        初始化 Session 管理器

        Args:
            max_workers: 最大并发 Session 数
        """
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()  # 使用可重入锁，避免嵌套调用死锁
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._callbacks: Dict[str, Callable] = {}  # session_id -> callback
        self._analysis_service = None

        # 从文件加载 sessions
        self._load_sessions()

    def _load_sessions(self):
        """从 JSON 文件加载 sessions"""
        if not SESSIONS_FILE.exists():
            return

        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            for session_data in data:
                session = Session.from_dict(session_data)
                # 如果 session 之前是 running 状态，标记为 error（因为服务器重启了）
                if session.status == SessionStatus.RUNNING:
                    session.status = SessionStatus.ERROR
                    session.error_msg = "服务器重启，分析中断"
                    session.current_agent = ""
                self._sessions[session.id] = session
        except Exception as e:
            print(f"加载 sessions 失败: {e}")

    def _save_sessions(self):
        """保存 sessions 到 JSON 文件"""
        try:
            # 确保目录存在
            SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

            with self._lock:
                data = [s.to_dict() for s in self._sessions.values()]

            with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存 sessions 失败: {e}")

    def _get_service(self):
        """延迟加载 AnalysisService"""
        if self._analysis_service is None:
            from .analysis_service import AnalysisService
            self._analysis_service = AnalysisService()
        return self._analysis_service

    def _get_next_agent(self, current_agent: str) -> str:
        """
        获取下一个要运行的 Agent

        Args:
            current_agent: 当前完成的 Agent 名称

        Returns:
            下一个 Agent 名称，如果没有则返回空字符串
        """
        try:
            idx = AGENT_ORDER.index(current_agent)
            if idx + 1 < len(AGENT_ORDER):
                return AGENT_ORDER[idx + 1]
        except ValueError:
            pass
        return ""

    def create_session(
        self,
        ticker: str,
        stock_name: str,
        market: str,
        start_date: str,
        end_date: str,
        user_id: str = "",
    ) -> Session:
        """
        创建新 Session

        Args:
            ticker: 股票代码
            stock_name: 股票名称
            market: 市场类型
            start_date: 开始日期
            end_date: 结束日期
            user_id: 所属用户

        Returns:
            新创建的 Session
        """
        session_id = str(uuid.uuid4())[:8]  # 短 ID
        session = Session(
            id=session_id,
            ticker=ticker,
            stock_name=stock_name,
            market=market,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

        with self._lock:
            self._sessions[session_id] = session

        self._save_sessions()
        return session

    def get_session(self, session_id: str, user_id: str = None, is_admin: bool = False) -> Optional[Session]:
        """
        获取 Session

        Args:
            session_id: Session ID
            user_id: 当前用户 ID（用于权限检查）
            is_admin: 是否是管理员

        Returns:
            Session 或 None（无权限或不存在）
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            # 管理员可以访问所有 session
            if is_admin:
                return session
            # 普通用户只能访问自己的 session
            if user_id and session.user_id and session.user_id != user_id:
                return None
            return session

    def get_all_sessions(self, user_id: str = None, is_admin: bool = False) -> List[Session]:
        """
        获取所有 Session（按创建时间降序）

        Args:
            user_id: 当前用户 ID（用于过滤）
            is_admin: 是否是管理员（可查看所有）

        Returns:
            Session 列表
        """
        with self._lock:
            if is_admin:
                # 管理员可以看到所有 session
                sessions = list(self._sessions.values())
            elif user_id:
                # 普通用户只能看到自己的 session
                sessions = [s for s in self._sessions.values() if s.user_id == user_id]
            else:
                # 没有 user_id 时返回空（向后兼容：也返回没有 user_id 的旧 session）
                sessions = [s for s in self._sessions.values() if not s.user_id]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def get_running_count(self, user_id: str = None, is_admin: bool = False) -> int:
        """
        获取正在运行的 Session 数量

        Args:
            user_id: 当前用户 ID（用于过滤）
            is_admin: 是否是管理员

        Returns:
            运行中的 session 数量
        """
        with self._lock:
            if is_admin:
                return sum(
                    1 for s in self._sessions.values()
                    if s.status == SessionStatus.RUNNING
                )
            elif user_id:
                return sum(
                    1 for s in self._sessions.values()
                    if s.status == SessionStatus.RUNNING and s.user_id == user_id
                )
            else:
                return sum(
                    1 for s in self._sessions.values()
                    if s.status == SessionStatus.RUNNING and not s.user_id
                )

    def delete_session(self, session_id: str) -> bool:
        """删除 Session"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save_sessions()
                return True
            return False

    def start_session(
        self,
        session_id: str,
        selected_analysts: List[str] = None,
        on_update: Callable[[Session], None] = None,
    ):
        """
        启动 Session 执行

        Args:
            session_id: Session ID
            selected_analysts: 启用的分析师列表
            on_update: 状态更新回调
        """
        session = self.get_session(session_id)
        if not session:
            return

        if on_update:
            self._callbacks[session_id] = on_update

        # 提交到线程池执行
        self._executor.submit(
            self._run_session,
            session_id,
            selected_analysts or ["market", "social", "news", "fundamentals"],
        )

    def _run_session(self, session_id: str, selected_analysts: List[str]):
        """
        执行 Session 分析（在后台线程中运行）

        Args:
            session_id: Session ID
            selected_analysts: 启用的分析师列表
        """
        session = self.get_session(session_id)
        if not session:
            return

        # 更新状态为运行中，设置第一个 Agent
        with self._lock:
            session.status = SessionStatus.RUNNING
            session.current_agent = AGENT_ORDER[0] if AGENT_ORDER else ""

        self._notify_update(session_id)

        try:
            service = self._get_service()

            # 流式分析
            for agent_name, content in service.analyze_stream(
                ticker=session.ticker,
                date=session.end_date,  # 使用结束日期作为分析日期
                market=session.market,
                selected_analysts=selected_analysts,
            ):
                if agent_name == "__FINAL__":
                    # 最终决策
                    with self._lock:
                        session.decision = content
                        session.status = SessionStatus.COMPLETED
                        session.current_agent = ""
                    self._notify_update(session_id)
                    return

                elif agent_name == "__QUOTA_ERROR__":
                    with self._lock:
                        session.status = SessionStatus.ERROR
                        session.error_msg = "API 额度已用完"
                        session.current_agent = ""
                    self._notify_update(session_id)
                    return

                elif agent_name == "__TIMEOUT_ERROR__":
                    with self._lock:
                        session.status = SessionStatus.ERROR
                        session.error_msg = "网络响应超时"
                        session.current_agent = ""
                    self._notify_update(session_id)
                    return

                elif agent_name == "__ERROR__":
                    with self._lock:
                        session.status = SessionStatus.ERROR
                        session.error_msg = content[:200]  # 限制错误信息长度
                        session.current_agent = ""
                    self._notify_update(session_id)
                    return

                else:
                    # Agent 输出
                    with self._lock:
                        session.progress.append(agent_name)
                        session.reports[agent_name] = content
                        # 设置为下一个要运行的 Agent
                        session.current_agent = self._get_next_agent(agent_name)
                    self._notify_update(session_id)

        except Exception as e:
            with self._lock:
                session.status = SessionStatus.ERROR
                session.error_msg = str(e)[:200]
                session.current_agent = ""
            self._notify_update(session_id)

    def _notify_update(self, session_id: str):
        """通知状态更新并保存"""
        # 保存到文件
        self._save_sessions()

        # 发布到 SSE
        global _sse_publisher
        if _sse_publisher:
            session = self.get_session(session_id)
            if session:
                try:
                    _sse_publisher(session_id, session.to_dict())
                except Exception:
                    pass  # 忽略 SSE 发布错误

        # 执行回调
        callback = self._callbacks.get(session_id)
        if callback:
            session = self.get_session(session_id)
            if session:
                try:
                    callback(session)
                except Exception:
                    pass  # 忽略回调错误

    def retry_session(
        self,
        session_id: str,
        selected_analysts: List[str] = None,
        on_update: Callable[[Session], None] = None,
    ):
        """
        重试失败的 Session

        Args:
            session_id: Session ID
            selected_analysts: 启用的分析师列表
            on_update: 状态更新回调
        """
        session = self.get_session(session_id)
        if not session:
            return

        # 重置 Session 状态
        with self._lock:
            session.status = SessionStatus.PENDING
            session.error_msg = ""
            session.progress = []
            session.reports = {}
            session.decision = ""
            session.current_agent = ""

        self._save_sessions()

        if on_update:
            self._callbacks[session_id] = on_update

        # 提交到线程池执行
        self._executor.submit(
            self._run_session,
            session_id,
            selected_analysts or ["market", "social", "news", "fundamentals"],
        )

    def clear_completed(self):
        """清除已完成的 Session"""
        with self._lock:
            to_delete = [
                sid for sid, s in self._sessions.items()
                if s.status in (SessionStatus.COMPLETED, SessionStatus.ERROR)
            ]
            for sid in to_delete:
                del self._sessions[sid]
                if sid in self._callbacks:
                    del self._callbacks[sid]

        if to_delete:
            self._save_sessions()

    def shutdown(self):
        """关闭管理器"""
        self._executor.shutdown(wait=False)


# 全局单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局 SessionManager 单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
