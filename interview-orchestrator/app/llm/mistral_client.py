import os
import requests
import json as json_module
from typing import List, Literal, Optional, Dict, Any, Generator

ChatRole = Literal["system", "user", "assistant"]

# Backend-Typen
BACKEND_LOCAL = "local"
BACKEND_MISTRAL_API = "mistral_api"


class LocalMistralResponse:
    """Wrapper-Klasse um die Antwort des lokalen Modells zu kapseln."""
    def __init__(self, content: str, model: str, usage: Dict[str, int] = None):
        self.choices = [LocalMistralChoice(content)]
        self.model = model
        self.usage = usage or {}


class StreamingChunk:
    """Wrapper für einen einzelnen Streaming-Chunk."""
    def __init__(self, content: str, done: bool = False):
        self.content = content
        self.done = done


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
    Unified Client für Mistral LLM - unterstützt sowohl lokales Modell als auch Mistral-API.
    
    Backends:
    - local: Lokales Modell via Ollama oder LM Studio (Standard)
    - mistral_api: Offizielle Mistral-API
    
    Beide Backends unterstützen Streaming.
    """
    def __init__(
        self, 
        base_url: Optional[str] = None, 
        model: str = None,
        api_key: Optional[str] = None,
        backend: str = BACKEND_LOCAL
    ):
        self._backend = backend
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")
        
        # Lokale Server-Konfiguration
        self._local_base_url = base_url or os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
        self._local_model = model or os.getenv("LOCAL_LLM_MODEL", "mistral-small")
        
        # Mistral-API-Konfiguration
        self._mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        self._mistral_model = os.getenv("MISTRAL_API_MODEL", "mistral-small-latest")
        
        # Erkenne Server-Typ für lokales Backend
        self._is_ollama = "11434" in self._local_base_url or "ollama" in self._local_base_url.lower()
        
        # API-Endpoint basierend auf Server-Typ
        if self._is_ollama:
            self._local_chat_endpoint = f"{self._local_base_url}/api/chat"
        else:
            self._local_chat_endpoint = f"{self._local_base_url}/v1/chat/completions"
        
        self._print_config()
    
    def _print_config(self):
        """Gibt die aktuelle Konfiguration aus."""
        print(f"[MistralClient] Initialisiert:")
        print(f"  - Aktives Backend: {self._backend}")
        if self._backend == BACKEND_LOCAL:
            print(f"  - Server: {self._local_base_url}")
            print(f"  - Modell: {self._local_model}")
            print(f"  - Endpoint: {self._local_chat_endpoint}")
        else:
            print(f"  - API-URL: {self._mistral_api_url}")
            print(f"  - Modell: {self._mistral_model}")
            print(f"  - API-Key: {'***' + self._api_key[-4:] if self._api_key else 'NICHT GESETZT'}")
    
    @property
    def backend(self) -> str:
        """Gibt das aktuelle Backend zurück."""
        return self._backend
    
    @property
    def model(self) -> str:
        """Gibt das aktuelle Modell zurück."""
        if self._backend == BACKEND_LOCAL:
            return self._local_model
        return self._mistral_model
    
    @property
    def base_url(self) -> str:
        """Gibt die aktuelle Base-URL zurück."""
        if self._backend == BACKEND_LOCAL:
            return self._local_base_url
        return self._mistral_api_url
    
    def set_backend(self, backend: str) -> bool:
        """
        Wechselt das Backend.
        
        Args:
            backend: "local" oder "mistral_api"
            
        Returns:
            True wenn erfolgreich, False wenn Backend nicht verfügbar
        """
        if backend not in [BACKEND_LOCAL, BACKEND_MISTRAL_API]:
            print(f"⚠️  Unbekanntes Backend: {backend}")
            return False
        
        # Prüfe Verfügbarkeit
        if backend == BACKEND_MISTRAL_API and not self._api_key:
            print("⚠️  Mistral-API-Key nicht gesetzt. Bitte MISTRAL_API_KEY setzen.")
            return False
        
        if backend == BACKEND_LOCAL and not self.is_local_available():
            print(f"⚠️  Lokales Modell unter {self._local_base_url} nicht erreichbar.")
            return False
        
        self._backend = backend
        print(f"✅ Backend gewechselt zu: {backend}")
        self._print_config()
        return True
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Gibt den Status beider Backends zurück."""
        return {
            "current": self._backend,
            "local": {
                "available": self.is_local_available(),
                "url": self._local_base_url,
                "model": self._local_model
            },
            "mistral_api": {
                "available": bool(self._api_key),
                "has_key": bool(self._api_key),
                "model": self._mistral_model
            }
        }
    
    def is_local_available(self) -> bool:
        """Prüft, ob der lokale LLM-Server erreichbar ist."""
        try:
            if self._is_ollama:
                response = requests.get(f"{self._local_base_url}/api/tags", timeout=5)
            else:
                response = requests.get(f"{self._local_base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def is_available(self) -> bool:
        """Prüft, ob das aktuelle Backend erreichbar ist."""
        if self._backend == BACKEND_LOCAL:
            return self.is_local_available()
        else:
            return bool(self._api_key)

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> LocalMistralResponse:
        """
        Sendet eine Chat-Completion-Anfrage.
        """
        if stream:
            raise ValueError("Für Streaming bitte complete_stream() verwenden")
        
        if self._backend == BACKEND_MISTRAL_API:
            return self._complete_mistral_api(messages, temperature, max_tokens, json_mode)
        elif self._is_ollama:
            return self._complete_ollama(messages, temperature, max_tokens, json_mode)
        else:
            return self._complete_openai_compatible(messages, temperature, max_tokens, json_mode)

    def complete_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Generator[StreamingChunk, None, None]:
        """
        Sendet eine Streaming Chat-Completion-Anfrage.
        Gibt einen Generator zurück, der einzelne Chunks yielded.
        """
        if self._backend == BACKEND_MISTRAL_API:
            yield from self._stream_mistral_api(messages, temperature, max_tokens)
        elif self._is_ollama:
            yield from self._stream_ollama(messages, temperature, max_tokens)
        else:
            yield from self._stream_openai_compatible(messages, temperature, max_tokens)

    # ==================== Mistral-API Methoden ====================
    
    def _complete_mistral_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: Optional[Dict[str, Any]],
    ) -> LocalMistralResponse:
        """Mistral-API Anfrage (nicht-streaming)."""
        payload = {
            "model": self._mistral_model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        if json_mode is not None:
            payload["response_format"] = json_mode
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }
        
        try:
            response = requests.post(
                self._mistral_api_url,
                json=payload,
                headers=headers,
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return LocalMistralResponse(content, self._mistral_model, usage)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Verbindung zur Mistral-API fehlgeschlagen.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise RuntimeError("Mistral-API-Key ungültig oder abgelaufen.")
            raise RuntimeError(f"Mistral-API Fehler: {e}")
        except Exception as e:
            raise RuntimeError(f"Fehler bei Mistral-API-Anfrage: {str(e)}")
    
    def _stream_mistral_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Generator[StreamingChunk, None, None]:
        """Mistral-API Streaming."""
        payload = {
            "model": self._mistral_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }
        
        try:
            response = requests.post(
                self._mistral_api_url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=300
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                    
                    if line_text.strip() == "[DONE]":
                        yield StreamingChunk("", True)
                        break
                    
                    try:
                        data = json_module.loads(line_text)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = data.get("choices", [{}])[0].get("finish_reason")
                        
                        if content:
                            yield StreamingChunk(content, finish_reason == "stop")
                        elif finish_reason == "stop":
                            yield StreamingChunk("", True)
                    except Exception:
                        continue
                        
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Verbindung zur Mistral-API fehlgeschlagen.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise RuntimeError("Mistral-API-Key ungültig.")
            raise RuntimeError(f"Mistral-API Streaming-Fehler: {e}")
        except Exception as e:
            raise RuntimeError(f"Fehler bei Mistral-API Streaming: {str(e)}")

    # ==================== Lokale Server Methoden ====================

    def _stream_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Generator[StreamingChunk, None, None]:
        """Ollama-spezifisches Streaming."""
        payload = {
            "model": self._local_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            }
        }
        
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            response = requests.post(
                self._local_chat_endpoint,
                json=payload,
                stream=True,
                timeout=300
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json_module.loads(line)
                        content = data.get("message", {}).get("content", "")
                        done = data.get("done", False)
                        
                        if content:
                            yield StreamingChunk(content, done)
                        elif done:
                            yield StreamingChunk("", True)
                    except Exception as e:
                        print(f"⚠️  Fehler beim Parsen von Stream-Chunk: {e}")
                        continue
                        
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self._local_base_url} fehlgeschlagen. "
                f"Stelle sicher, dass Ollama läuft."
            )
        except Exception as e:
            raise RuntimeError(f"Fehler bei Streaming-Anfrage: {str(e)}")

    def _stream_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Generator[StreamingChunk, None, None]:
        """OpenAI-kompatibles Streaming (LM Studio, vLLM, etc.)."""
        payload = {
            "model": self._local_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        try:
            response = requests.post(
                self._local_chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=300
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                    
                    if line_text.strip() == "[DONE]":
                        yield StreamingChunk("", True)
                        break
                    
                    try:
                        data = json_module.loads(line_text)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = data.get("choices", [{}])[0].get("finish_reason")
                        
                        if content:
                            yield StreamingChunk(content, finish_reason == "stop")
                        elif finish_reason == "stop":
                            yield StreamingChunk("", True)
                    except Exception:
                        continue
                        
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self._local_base_url} fehlgeschlagen."
            )
        except Exception as e:
            raise RuntimeError(f"Fehler bei Streaming-Anfrage: {str(e)}")

    def _complete_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: Optional[Dict[str, Any]],
    ) -> LocalMistralResponse:
        """Ollama-spezifische API-Anfrage."""
        payload = {
            "model": self._local_model,
            "messages": messages,
            "stream": False,
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
                self._local_chat_endpoint,
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            
            content = data.get("message", {}).get("content", "")
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            }
            
            return LocalMistralResponse(content, self._local_model, usage)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self._local_base_url} fehlgeschlagen. "
                f"Stelle sicher, dass Ollama läuft: 'ollama serve' und das Modell geladen ist: 'ollama run {self._local_model}'"
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
    ) -> LocalMistralResponse:
        """OpenAI-kompatible API-Anfrage (für LM Studio, vLLM, etc.)."""
        payload = {
            "model": self._local_model,
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
                self._local_chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return LocalMistralResponse(content, self._local_model, usage)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Verbindung zu {self._local_base_url} fehlgeschlagen. "
                f"Stelle sicher, dass der lokale LLM-Server läuft."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Timeout bei der Anfrage an das lokale Modell.")
        except Exception as e:
            raise RuntimeError(f"Fehler bei lokaler LLM-Anfrage: {str(e)}")

    def list_models(self) -> List[str]:
        """Listet verfügbare Modelle auf dem lokalen Server."""
        try:
            if self._is_ollama:
                response = requests.get(f"{self._local_base_url}/api/tags", timeout=10)
                response.raise_for_status()
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            else:
                response = requests.get(f"{self._local_base_url}/v1/models", timeout=10)
                response.raise_for_status()
                data = response.json()
                return [model["id"] for model in data.get("data", [])]
        except:
            return []
