"""核心引擎 - 串联录音、识别、LLM处理的完整流程"""
import re
import time
import threading
import pyperclip
import pyautogui
from enum import Enum
from voicetype.core.config import load_config
from voicetype.core.recorder import AudioRecorder
from voicetype.core.stt import SpeechToText
from voicetype.core.llm import OllamaLLM


class VoiceMode(Enum):
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"
    REWRITE = "rewrite"


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def _quick_punctuate(text: str) -> str:
    """对短文本做简单标点修正，不走 LLM"""
    text = text.strip()
    if not text:
        return text
    # 去掉常见语气词
    for filler in ["嗯", "啊", "那个", "就是说", "然后那个"]:
        text = text.replace(filler, "")
    text = text.strip()
    # 如果末尾没标点，加句号
    if text and text[-1] not in "。！？!?.，,、；;：:…":
        if any(c in text for c in "吗呢吧啊"):
            text += "？"
        else:
            text += "。"
    return text


class VoiceTypeEngine:
    """VoiceType 核心引擎"""

    # 短文本阈值：低于此字数的 TRANSCRIBE 直接加标点，不走 LLM
    SHORT_TEXT_THRESHOLD = 25

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.recorder = AudioRecorder()
        self.stt = SpeechToText(
            model_size=self.config["whisper_model"],
            device=self.config["whisper_device"],
            language=self.config.get("language"),
        )
        self.llm = OllamaLLM(
            model=self.config["llm_model"],
            base_url=self.config["ollama_url"],
        )
        self._on_status = None
        self._on_result = None
        self._task_id = 0
        self._task_lock = threading.Lock()

    def new_task_id(self) -> int:
        with self._task_lock:
            self._task_id += 1
            return self._task_id

    def is_task_valid(self, task_id: int) -> bool:
        return task_id == self._task_id

    def set_callbacks(self, on_status=None, on_result=None):
        self._on_status = on_status
        self._on_result = on_result

    def _status(self, msg: str):
        if self._on_status:
            self._on_status(msg)

    def ensure_ready(self) -> bool:
        self._status("正在检查 Ollama...")
        if not self.llm.ensure_ready():
            return False
        # 预热模型 —— 发一个极短请求让模型加载到显存
        self._status("正在预热 AI 模型...")
        try:
            self.llm.chat(
                [{"role": "user", "content": "hi"}],
                temperature=0, max_tokens=1
            )
        except Exception:
            pass
        self._status("所有组件就绪，可以使用了!")
        return True

    # ── 录音控制 ──
    def start_recording(self):
        self._status("正在录音...")
        self.recorder.start()

    def stop_recording(self) -> bytes:
        self._status("录音结束，处理中...")
        return self.recorder.stop()

    # ── 获取选中文字 ──
    def get_selected_text(self) -> str:
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass

        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)

        try:
            selected = pyperclip.paste()
        except Exception:
            return ""

        if selected != old_clip:
            return selected
        return ""

    # ── 自动输入到当前窗口 ──
    def type_text(self, text: str):
        if not text.strip():
            return
        text = text.replace("**", "").replace("__", "")
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")

    # ── 核心处理流程 ──
    def process_audio(self, audio_bytes: bytes, mode: VoiceMode, task_id: int = 0, **kwargs) -> str:
        if not audio_bytes or len(audio_bytes) < 1000:
            self._status("未检测到有效音频")
            return ""

        if task_id and not self.is_task_valid(task_id):
            return ""

        # 1. 语音识别
        self._status("正在识别语音...")
        result = self.stt.transcribe(audio_bytes)
        raw_text = result["text"]

        if not raw_text.strip():
            self._status("未识别到语音")
            return ""

        if task_id and not self.is_task_valid(task_id):
            return ""

        self._status(f"识别到: {raw_text[:40]}...")

        # 2. 根据模式处理
        if mode == VoiceMode.TRANSCRIBE:
            # 短文本直接加标点，不走 LLM —— 省 3 秒
            if len(raw_text) <= self.SHORT_TEXT_THRESHOLD:
                final = _quick_punctuate(raw_text)
            else:
                self._status("正在整理文本...")
                final = self.llm.refine_text(raw_text)

        elif mode == VoiceMode.TRANSLATE:
            target_lang = kwargs.get("target_lang", self.config["translate_target"])
            self._status("正在翻译...")
            final = self.llm.translate(raw_text, target_lang)

        elif mode == VoiceMode.REWRITE:
            selected_text = kwargs.get("selected_text", "")
            if not selected_text:
                self._status("未获取到选中文字")
                return ""
            self._status("AI 正在改写...")
            final = self.llm.rewrite(selected_text, raw_text)

        else:
            final = raw_text

        if task_id and not self.is_task_valid(task_id):
            return ""

        final = final.strip().replace("**", "").replace("__", "")
        return final

    def stop_and_process(self, mode: VoiceMode, task_id: int = 0, **kwargs) -> str:
        audio = self.stop_recording()

        if not self.recorder.has_voice():
            self._status("未检测到语音")
            return ""

        result = self.process_audio(audio, mode, task_id=task_id, **kwargs)

        if result and self.is_task_valid(task_id):
            if self.config.get("auto_paste", True):
                self.type_text(result)
            if self._on_result:
                self._on_result(result)

        return result

    def cleanup(self):
        self.recorder.cleanup()
