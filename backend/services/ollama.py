"""
Ollama service for local LLM inference.
"""

import httpx
import json
from typing import AsyncGenerator, Dict, Any, Optional
from ..config import settings


class OllamaService:
    """Service for interacting with Ollama API."""

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.llm_model

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False
    ) -> str:
        """
        Generate text using Ollama.

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

        request_body = {
            "model": self.model,
            "messages": messages,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            },
            "stream": stream
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            if stream:
                return self._generate_stream(client, request_body)
            else:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=request_body
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")

    async def _generate_stream(
        self,
        client: httpx.AsyncClient,
        request_body: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Generate text in streaming mode."""
        async with client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=request_body
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        continue

    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings using Ollama.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        request_body = {
            "model": "nomic-embed-text",  # Or another embedding model
            "prompt": text
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json=request_body
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])

    async def health_check(self) -> bool:
        """Check if Ollama service is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False

    async def list_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
        except:
            return []