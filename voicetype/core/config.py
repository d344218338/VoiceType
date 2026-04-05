"""配置管理模块"""
import json
import os
from pathlib import Path
from datetime import datetime

APP_NAME = "VoiceType"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
APP_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"

# 版本标识: "personal" 或 "public"
EDITION = os.environ.get("VOICETYPE_EDITION", "personal")

# 默认模型配置
MODEL_CONFIGS = {
    "personal": {
        "llm_model": "gemma4:latest",
        "llm_provider": "ollama",
        "whisper_model": "base",
    },
    "public": {
        "llm_model": "qwen2.5:1.5b",
        "llm_provider": "ollama",
        "whisper_model": "base",
    },
}

DEFAULT_CONFIG = {
    "edition": EDITION,
    # 语音识别
    "whisper_model": MODEL_CONFIGS[EDITION]["whisper_model"],
    "whisper_device": "auto",  # auto, cpu, cuda
    "language": "zh",  # 默认识别语言，None=自动检测
    # LLM
    "llm_provider": "ollama",
    "llm_model": MODEL_CONFIGS[EDITION]["llm_model"],
    "ollama_url": "http://localhost:11434",
    # 翻译
    "translate_target": "en",  # 默认翻译目标语言
    # 快捷键（默认使用右Alt组合）
    "hotkey_transcribe": "ralt",           # 语音整理：单独按住右Alt
    "hotkey_translate": "ralt+rshift",     # 语音翻译：右Alt+右Shift
    "hotkey_assistant": "ralt+rctrl",       # AI 改写：右Alt+右Ctrl
    # 录音
    "sample_rate": 16000,
    "channels": 1,
    # UI
    "floating_bar": True,
    "auto_paste": True,  # 识别完自动粘贴
    "theme": "dark",
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        merged = {**DEFAULT_CONFIG, **saved}
        return merged
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_state() -> dict:
    default_state = {
        "first_run": True,
        "install_date": datetime.now().isoformat(),
        "donation_shown_install": False,
        "donation_shown_periodic": False,
        "donation_last_shown": None,
        "total_usage_count": 0,
    }
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return {**default_state, **saved}
    save_state(default_state)
    return default_state


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
