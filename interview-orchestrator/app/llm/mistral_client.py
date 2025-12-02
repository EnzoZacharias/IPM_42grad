import os
import requests
from typing import List, Literal, Optional, Dict, Any

ChatRole = Literal["system", "user", "assistant"]


class LocalMistralResponse:
    """Wrapper-Klasse um die Antwort des lokalen Modells zu kapseln."""
    def __init__(self, content: str, model: str, usage: Dict[str, int] = None):
        self.choices = [LocalMistralChoice(content)]
        self.model = model
        self.usage = usage or {}


class LocalMistralChoice:
    """Wrapper für eine einzelne Antwort-Choice."""
    def __init__(self, content: str):
        self.message = LocalMistralMessage(content)
        self.finish_reason = "stop"


class LocalMistralMessage:
    """Wrapper für die Message in einer Choice."""
    def __init__(self, content: str):
        self.content = content
        self.role = "assistant"


class MistralClient:
    """
    Client für lokales Mistral-Modell (z.B. via Ollama oder LM Studio).
    Kommuniziert über OpenAI-kompatible REST-API.
    
    Unterstützte lokale Server:
    - Ollama: ollama run mistral-small (Standard-Port: 11434)
    - LM Studio: (Standard-Port: 1234)
    - vLLM: (konfigurierbar)
    """
    def __init__(
        self, 
        base_url: Optional[str] = None, 
        model: str = None,
        api_key: Optional[str] = None  # Für Kompatibilität, wird bei lokalem Modell ignoriert
    ):
        # Lokale Server-URL (Standard: Ollama)
        self.base_url = base_url or os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
        self.model = model or os.getenv("LOCAL_LLM_MODEL", "mistral-small")
        
        # Erkenne Server-Typ anhand der URL
        self._is_ollama = "11434" in self.base_url or "ollama" in self.base_url.lower()
        
        # API-Endpoint basierend auf Server-Typ
        if self._is_ollama:
            self._chat_endpoint = f"{self.base_url}/api/chat"
        else:
            # OpenAI-kompatible API (LM Studio, vLLM, etc.)
            self._chat_endpoint = f"{self.base_url}/v1/chat/completions"
        
        print(f"[MistralClient] Lokales Modell initialisiert:")
        print(f"  - Server: {self.base_url}")
        print(f"  - Modell: {self.model}")
        print(f"  - Endpoint: {self._chat_endpoint}")

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> LocalMistralResponse:
        """
        Sendet eine Chat-Completion-Anfrage an das lokale Modell.
        """
        if self._is_ollama:
            return self._complete_ollama(messages, temperature, max_tokens, json_mode, stream)
        else:
            return self._complete_openai_compatible(messages, temperature, max_tokens, json_mode, stream)

    def _complete_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: Optional[Dict[str, Any]],
        stream: bool,
    ) -> LocalMistralResponse:
        """Ollama-spezifische API-Anfrage."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,  # Streaming hier deaktiviert für einfache Antwort
            "options": {
                "temperature": temperature,
            }
        }
        
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        
        if json_mode is not None:
            payload["format"] = "json"
        
        try:
            response = requests.post(
                self._chat_endpoint,
                json=payload,
                timeout=300  # 5 Minuten Timeout für lange Antworten
            )
            response.raise_for_status()
            data = response.json()
            
            content = data.get("message", {}).get("content", "")
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            }
            
            return LocalMistralResponse(content, self.model, usage)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self.base_url} fehlgeschlagen. "
                f"Stelle sicher, dass Ollama läuft: 'ollama serve' und das Modell geladen ist: 'ollama run {self.model}'"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Timeout bei der Anfrage an das lokale Modell.")
        except Exception as e:
            raise RuntimeError(f"Fehler bei lokaler LLM-Anfrage: {str(e)}")

    def _complete_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: Optional[Dict[str, Any]],
        stream: bool,
    ) -> LocalMistralResponse:
        """OpenAI-kompatible API-Anfrage (für LM Studio, vLLM, etc.)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        if json_mode is not None:
            payload["response_format"] = json_mode
        
        try:
            response = requests.post(
                self._chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return LocalMistralResponse(content, self.model, usage)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self.base_url} fehlgeschlagen. "
                f"Stelle sicher, dass der lokale LLM-Server läuft."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Timeout bei der Anfrage an das lokale Modell.")
        except Exception as e:
            raise RuntimeError(f"Fehler bei lokaler LLM-Anfrage: {str(e)}")

    def is_available(self) -> bool:
        """Prüft, ob der lokale LLM-Server erreichbar ist."""
        try:
            if self._is_ollama:
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            else:
                response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False

    def list_models(self) -> List[str]:
        """Listet verfügbare Modelle auf dem lokalen Server."""
        try:
            if self._is_ollama:
                response = requests.get(f"{self.base_url}/api/tags", timeout=10)
                response.raise_for_status()
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            else:
                response = requests.get(f"{self.base_url}/v1/models", timeout=10)
                response.raise_for_status()
                data = response.json()
                return [model["id"] for model in data.get("data", [])]
        except:
            return []
