"""语音识别模块 - 多后端支持，优先用最快的"""
import io
import wave
import numpy as np


class SpeechToText:
    """语音转文字 - Google API 优先，faster-whisper 离线回退"""

    def __init__(self, model_size="base", device="auto", language=None):
        self.language = language or "zh-CN"
        self.model_size = model_size
        self.device = device
        self._whisper_model = None

    def _ensure_model(self):
        pass

    def _trim_silence(self, audio_bytes: bytes, threshold=400) -> bytes:
        """裁掉音频前后的静音段，减少发送给 STT 的数据量"""
        try:
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                params = wf.getparams()
                raw = wf.readframes(wf.getnframes())

            samples = np.frombuffer(raw, dtype=np.int16)
            if len(samples) == 0:
                return audio_bytes

            # 用 chunk 级别检测（每 1600 个采样点 = 0.1秒@16kHz）
            chunk = 1600
            energies = []
            for i in range(0, len(samples), chunk):
                seg = samples[i:i + chunk]
                energies.append(np.sqrt(np.mean(seg.astype(float) ** 2)))

            # 找到第一个和最后一个有声音的 chunk
            start_chunk = 0
            end_chunk = len(energies) - 1
            for i, e in enumerate(energies):
                if e > threshold:
                    start_chunk = max(0, i - 2)  # 保留前 0.2 秒缓冲
                    break

            for i in range(len(energies) - 1, -1, -1):
                if energies[i] > threshold:
                    end_chunk = min(len(energies) - 1, i + 2)  # 保留后 0.2 秒缓冲
                    break

            # 裁剪
            start_sample = start_chunk * chunk
            end_sample = min((end_chunk + 1) * chunk, len(samples))

            if end_sample - start_sample < chunk:
                return audio_bytes  # 太短不裁

            trimmed = samples[start_sample:end_sample].tobytes()

            out = io.BytesIO()
            with wave.open(out, "wb") as wf:
                wf.setparams(params)
                wf.writeframes(trimmed)
            return out.getvalue()
        except Exception:
            return audio_bytes

    def transcribe(self, audio_bytes: bytes) -> dict:
        """识别音频，优先 Google API，失败回退 Whisper"""
        if not audio_bytes or len(audio_bytes) < 1000:
            return {"text": "", "language": "", "segments": []}

        # 裁掉前后静音
        audio_bytes = self._trim_silence(audio_bytes)

        # 方案1: Google 免费语音识别
        try:
            text = self._google_recognize(audio_bytes)
            if text:
                return {"text": text, "language": self.language, "segments": []}
        except Exception:
            pass

        # 方案2: 本地 faster-whisper
        try:
            return self._whisper_recognize(audio_bytes)
        except Exception:
            pass

        return {"text": "", "language": "", "segments": []}

    def _google_recognize(self, audio_bytes: bytes) -> str:
        """Google 免费语音识别"""
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)

        lang_map = {
            "zh": "zh-CN", "zh-CN": "zh-CN", "zh-TW": "zh-TW",
            "en": "en-US", "ja": "ja-JP", "ko": "ko-KR",
            "fr": "fr-FR", "de": "de-DE", "es": "es-ES",
            "ru": "ru-RU", "pt": "pt-BR",
        }
        lang = lang_map.get(self.language, self.language)
        if "-" not in lang and len(lang) == 2:
            lang = lang_map.get(lang, f"{lang}-{lang.upper()}")

        return recognizer.recognize_google(audio, language=lang)

    def _whisper_recognize(self, audio_bytes: bytes) -> dict:
        """本地 faster-whisper 回退"""
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
        texts = [seg.text.strip() for seg in segments]

        return {
            "text": " ".join(texts),
            "language": info.language if hasattr(info, "language") else "",
            "segments": [],
        }

    def transcribe_file(self, filepath: str) -> dict:
        with open(filepath, "rb") as f:
            return self.transcribe(f.read())
