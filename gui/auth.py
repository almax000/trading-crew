"""
自定义认证模块

提供自定义登录页面替代 Gradio 的 HTTP Basic Auth，
支持登出功能。
"""

from typing import Tuple, Optional
from .config import INVITE_CODES


def authenticate(username: str, password: str) -> Tuple[bool, str]:
    """
    验证用户登录

    Args:
        username: 用户名
        password: 密码

    Returns:
        (success, message) - 登录是否成功及提示信息
    """
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return False, "请输入用户名和密码"

    if (username, password) in INVITE_CODES:
        return True, f"欢迎，{username}"

    return False, "用户名或密码错误"


def get_username_from_session(session: dict) -> Optional[str]:
    """
    从 session 获取用户名

    Args:
        session: Gradio session dict

    Returns:
        用户名或 None
    """
    return session.get("username")


def is_logged_in(session: dict) -> bool:
    """
    检查是否已登录

    Args:
        session: Gradio session dict

    Returns:
        是否已登录
    """
    return bool(session.get("logged_in", False))


def create_session(username: str) -> dict:
    """
    创建登录 session

    Args:
        username: 用户名

    Returns:
        session dict
    """
    return {
        "logged_in": True,
        "username": username,
    }


def clear_session() -> dict:
    """
    清空 session（登出）

    Returns:
        空 session dict
    """
    return {
        "logged_in": False,
        "username": "",
    }
