import os
from typing import List, Literal, Optional, Dict, Any
from mistralai import Mistral

ChatRole = Literal["system", "user", "assistant"]

class MistralClient:
    """
    Dünner Wrapper um die mistralai-SDK.
    Unterstützt: Chat Completion, Streaming, JSON-Mode.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY fehlt (siehe .env).")
        self.model = model or os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        self._client = Mistral(api_key=self.api_key)

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode is not None:
            kwargs["response_format"] = json_mode
        return self._client.chat.complete(**kwargs)
