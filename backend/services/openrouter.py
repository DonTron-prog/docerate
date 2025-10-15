"""
OpenRouter service for LLM inference.
Provides access to multiple models through a unified API.
"""

import httpx
import json
from typing import AsyncGenerator, Dict, Any, Optional
from ..config import settings


class OpenRouterService:
    """Service for interacting with OpenRouter API."""

    def __init__(self):
        # Ensure API key is always a string, not bytes
        api_key = settings.openrouter_api_key
        if api_key is None or api_key == "":
            print(f"WARNING: OpenRouter API key is not set!")
            self.api_key = ""
        elif isinstance(api_key, bytes):
            self.api_key = api_key.decode('utf-8').strip()
        else:
            self.api_key = str(api_key).strip()

        self.model = settings.openrouter_model
        self.base_url = "https://openrouter.ai/api/v1"
        self.site_url = settings.openrouter_site_url
        self.app_name = settings.openrouter_app_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False
    ) -> str:
        """
        Generate text using OpenRouter.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
            "Content-Type": "application/json"
        }

        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            if stream:
                return self._generate_stream(client, headers, request_body)
            else:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=request_body
                )
                response.raise_for_status()
                data = response.json()

                # OpenRouter returns OpenAI-compatible format
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                return ""

    async def _generate_stream(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        request_body: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Generate text in streaming mode."""
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=request_body,
            timeout=60.0
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line_data = line[6:]  # Remove "data: " prefix
                    if line_data == "[DONE]":
                        break
                    try:
                        data = json.loads(line_data)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """Check if OpenRouter service is available."""
        if not self.api_key:
            print("OpenRouter health check skipped: API key not configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check if we can list models
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )
                return response.status_code == 200
        except Exception as e:
            print(f"OpenRouter health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available OpenRouter models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )
                response.raise_for_status()
                data = response.json()

                # OpenRouter returns models in OpenAI format
                if "data" in data:
                    return [model["id"] for model in data["data"]]
                return []
        except Exception as e:
            print(f"Failed to list OpenRouter models: {e}")
            return []

    async def get_usage(self) -> Dict[str, Any]:
        """Get usage statistics from OpenRouter."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Failed to get OpenRouter usage: {e}")
            return {}