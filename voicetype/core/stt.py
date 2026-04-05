"""语音识别模块 - 多后端支持，优先用最快的"""
import io


class SpeechToText:
    """语音转文字 - 自动选择最快的方案"""

    def __init__(self, model_size="base", device="auto", language=None):
        self.language = language or "zh-CN"
        self.model_size = model_size
        self.device = device
        self._whisper_model = None

    def _ensure_model(self):
        """预加载（仅在需要本地 whisper 时）"""
        pass  # Google API 不需要预加载

    def is_silent(self, audio_bytes: bytes, threshold=400) -> bool:
        """快速检测音频是否全是静音"""
        import numpy as np
        import wave
        try:
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            samples = np.frombuffer(raw, dtype=np.int16)
            rms = np.sqrt(np.mean(samples.astype(float) ** 2))
            return rms < threshold
        except Exception:
            return False

    def transcribe(self, audio_bytes: bytes) -> dict:
        """
        识别音频，优先用 Google 免费 API（快），失败则回退到本地 Whisper。
        """
        if not audio_bytes or len(audio_bytes) < 1000:
            return {"text": "", "language": "", "segments": []}

        # 快速静音检测 - 如果音频几乎没声音就立即返回
        if self.is_silent(audio_bytes):
            return {"text": "", "language": "", "segments": []}

        # 方案1: Google 免费语音识别（最快）
        try:
            text = self._google_recognize(audio_bytes)
            if text:
                return {"text": text, "language": self.language, "segments": []}
        except Exception:
            pass

        # 方案2: 本地 faster-whisper（离线可用）
        try:
            return self._whisper_recognize(audio_bytes)
        except Exception:
            pass

        return {"text": "", "language": "", "segments": []}

    def _google_recognize(self, audio_bytes: bytes) -> str:
        """Google 免费语音识别 - 无需 API key，速度快"""
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        # 直接用内存 BytesIO，不写临时文件
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)

        # language 映射
        lang_map = {
            "zh": "zh-CN", "zh-CN": "zh-CN", "zh-TW": "zh-TW",
            "en": "en-US", "ja": "ja-JP", "ko": "ko-KR",
            "fr": "fr-FR", "de": "de-DE", "es": "es-ES",
            "ru": "ru-RU", "pt": "pt-BR",
        }
        lang = lang_map.get(self.language, self.language)
        if "-" not in lang and len(lang) == 2:
            lang = lang_map.get(lang, f"{lang}-{lang.upper()}")

        text = recognizer.recognize_google(audio, language=lang)
        return text

    def _whisper_recognize(self, audio_bytes: bytes) -> dict:
        """本地 faster-whisper 回退方案"""
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            device = self.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            compute = "float16" if device == "cuda" else "int8"
            self._whisper_model = WhisperModel(self.model_size, device=device, compute_type=compute)

        buf = io.BytesIO(audio_bytes)
        lang = self.language if self.language and len(self.language) == 2 else None
        segments, info = self._whisper_model.transcribe(buf, language=lang, beam_size=5, vad_filter=True)

        texts = []
        for seg in segments:
            texts.append(seg.text.strip())

        return {
            "text": " ".join(texts),
            "language": info.language if hasattr(info, "language") else "",
            "segments": [],
        }

    def transcribe_file(self, filepath: str) -> dict:
        with open(filepath, "rb") as f:
            return self.transcribe(f.read())
