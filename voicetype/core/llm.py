"""LLM 集成模块 - 通过 Ollama 提供文本整理、翻译、AI助手功能"""
import json
import subprocess
import sys
import os
import shutil
import time
import urllib.request
import urllib.error


class OllamaLLM:
    """Ollama LLM 客户端"""

    def __init__(self, model: str = "gemma3:27b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _request(self, endpoint: str, data: dict, stream: bool = False) -> dict | str:
        url = f"{self.base_url}{endpoint}"
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if stream:
                    full_response = []
                    for line in resp:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response.append(chunk["response"])
                        if "message" in chunk:
                            full_response.append(chunk["message"].get("content", ""))
                    return "".join(full_response)
                else:
                    return json.loads(resp.read())
        except urllib.error.URLError as e:
            raise ConnectionError(f"无法连接 Ollama ({self.base_url}): {e}")

    def is_ollama_running(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    def start_ollama(self) -> bool:
        """尝试启动 Ollama"""
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            # Windows 常见路径
            for p in [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Ollama\ollama.exe"),
                r"C:\Program Files\Ollama\ollama.exe",
            ]:
                if os.path.exists(p):
                    ollama_path = p
                    break

        if not ollama_path:
            return False

        subprocess.Popen(
            [ollama_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # 等待启动
        for _ in range(15):
            time.sleep(1)
            if self.is_ollama_running():
                return True
        return False

    def ensure_ready(self) -> bool:
        """确保 Ollama 已启动且模型已下载"""
        if not self.is_ollama_running():
            print("Ollama 未运行，正在尝试启动...")
            if not self.start_ollama():
                print("❌ 无法启动 Ollama。请先安装: https://ollama.com")
                return False
            print("✅ Ollama 已启动")

        if not self.is_model_available():
            print(f"模型 {self.model} 未安装，正在下载（这可能需要几分钟）...")
            return self.pull_model()
        return True

    def is_model_available(self) -> bool:
        try:
            result = self._request("/api/tags", {})
            if isinstance(result, str):
                result = json.loads(result)
            models = result.get("models", [])
            model_base = self.model.split(":")[0]
            for m in models:
                if m["name"].startswith(model_base):
                    return True
            return False
        except Exception:
            return False

    def pull_model(self, callback=None) -> bool:
        """下载模型"""
        try:
            url = f"{self.base_url}/api/pull"
            data = json.dumps({"name": self.model, "stream": True}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    try:
                        chunk = json.loads(line)
                        status = chunk.get("status", "")
                        if "total" in chunk and "completed" in chunk:
                            pct = chunk["completed"] / chunk["total"] * 100
                            msg = f"\r⬇️  {status}: {pct:.1f}%"
                        else:
                            msg = f"\r⬇️  {status}"
                        if callback:
                            callback(msg, chunk)
                        else:
                            print(msg, end="", flush=True)
                    except json.JSONDecodeError:
                        pass
            print(f"\n✅ 模型 {self.model} 下载完成!")
            return True
        except Exception as e:
            print(f"\n❌ 模型下载失败: {e}")
            return False

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 0) -> str:
        """通用聊天接口"""
        options = {"temperature": temperature}
        if max_tokens > 0:
            options["num_predict"] = max_tokens
        data = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        return self._request("/api/chat", data, stream=True)

    def refine_text(self, raw_text: str, context: str = "") -> str:
        """整理语音转写的文字 - 修正语法、去口语化、排版、保持原意"""
        # 短文本用精简 prompt，减少 LLM 思考时间
        if len(raw_text) < 80:
            system_prompt = "把语音识别文本整理成通顺的书面文字。只修正错字、去语气词、加标点。不加问候语，不加解释，不用markdown，直接输出结果。"
        else:
            system_prompt = """把语音识别文本整理成通顺的书面文字。

规则：修正错字、去语气词（嗯啊那个等）、加标点、较长时分段、多要点时编号。
严格保持原意，不添加问候语/敬语/解释/评论，不用markdown格式，直接输出纯文本。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text},
        ]
        max_tok = max(len(raw_text) * 2, 200)
        return self.chat(messages, temperature=0.3, max_tokens=max_tok)

    def translate(self, text: str, target_lang: str = "en") -> str:
        """翻译文本"""
        lang_names = {
            "en": "English", "zh": "中文", "ja": "日本語", "ko": "한국어",
            "fr": "Français", "de": "Deutsch", "es": "Español", "ru": "Русский",
            "pt": "Português", "it": "Italiano", "ar": "العربية", "th": "ไทย",
            "vi": "Tiếng Việt",
        }
        target_name = lang_names.get(target_lang, target_lang)

        system_prompt = f"""将用户输入的文本翻译为 {target_name}。

规则：
1. 只输出翻译结果，不要加任何解释、前缀或问候语
2. 翻译要自然流畅，符合目标语言的表达习惯
3. 保持原文的语气和风格
4. 不要使用markdown格式"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        max_tok = max(len(text) * 3, 200)
        return self.chat(messages, temperature=0.3, max_tokens=max_tok)

    def ask(self, question: str, context: str = "") -> str:
        """AI 助手问答"""
        system_prompt = """你是一个智能AI助手。简洁、准确地回答用户的问题。如果问题不清晰，尝试给出最合理的回答。"""

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"上下文信息：{context}"})
            messages.append({"role": "assistant", "content": "好的，我已了解上下文。"})
        messages.append({"role": "user", "content": question})
        return self.chat(messages, temperature=0.7)

    def rewrite(self, original_text: str, voice_instruction: str) -> str:
        """AI 改写 - 根据语音指令改写选中的文字"""
        system_prompt = """你是一个文字改写工具。用户给你原文和语音指令，按照指令改写原文。

规则：
1. 严格按照用户的语音指令来改写
2. 只输出改写后的结果，不要加任何解释、前缀、后缀或问候语
3. 如果指令是"润色"，就让文字更通顺、更有逻辑
4. 如果指令是"补充"，在保持原意的基础上补充完善
5. 如果指令是"缩写/精简"，就提炼核心内容
6. 如果指令不明确，默认做润色处理
7. 不要使用markdown格式（不要用**加粗**等）"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"原文：\n{original_text}\n\n指令：{voice_instruction}"},
        ]
        return self.chat(messages, temperature=0.4)
