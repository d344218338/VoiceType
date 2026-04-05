"""打赏码弹窗模块 - 仅公开版使用"""
import os
from datetime import datetime, timedelta
from voicetype.core.config import load_state, save_state, EDITION


DONATION_INTERVAL_DAYS = 30  # 周期性提醒间隔（天）


def should_show_donation() -> bool:
    """判断是否应该显示打赏码"""
    if EDITION != "public":
        return False

    state = load_state()

    # 首次运行
    if state.get("first_run", True):
        return True

    # 周期性提醒（每30天最多一次）
    if not state.get("donation_shown_periodic", False):
        install_date = datetime.fromisoformat(state.get("install_date", datetime.now().isoformat()))
        if datetime.now() - install_date > timedelta(days=DONATION_INTERVAL_DAYS):
            return True

    # 已显示过周期性提醒，检查是否需要再次显示
    last_shown = state.get("donation_last_shown")
    if last_shown:
        last_dt = datetime.fromisoformat(last_shown)
        if datetime.now() - last_dt > timedelta(days=DONATION_INTERVAL_DAYS):
            return True

    return False


def mark_donation_shown():
    """标记打赏码已显示"""
    state = load_state()
    state["first_run"] = False
    state["donation_last_shown"] = datetime.now().isoformat()
    if not state.get("donation_shown_periodic"):
        install_date = datetime.fromisoformat(state.get("install_date", datetime.now().isoformat()))
        if datetime.now() - install_date > timedelta(days=DONATION_INTERVAL_DAYS):
            state["donation_shown_periodic"] = True
    save_state(state)


def get_donation_html(qr_path: str = None) -> str:
    """返回打赏弹窗的 HTML 内容"""
    return f"""
    <div style="text-align: center; padding: 20px; font-family: -apple-system, sans-serif;">
        <h2 style="color: #333; margin-bottom: 10px;">感谢使用 VoiceType! 🎙️</h2>
        <p style="color: #666; font-size: 14px; line-height: 1.6;">
            VoiceType 是完全免费的开源工具。<br>
            如果觉得好用，可以请作者喝杯咖啡 ☕
        </p>
        <div style="margin: 20px 0;">
            <img src="{qr_path or 'donation_qr.png'}"
                 style="width: 200px; height: 200px; border-radius: 8px; border: 1px solid #ddd;">
        </div>
        <p style="color: #999; font-size: 12px;">关闭后不会再打扰你的正常使用</p>
    </div>
    """
