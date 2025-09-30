"""
AWS Bedrock service for production LLM inference.
"""

import json
import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from ..config import settings


class BedrockService:
    """Service for interacting with AWS Bedrock."""

    def __init__(self):
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=settings.aws_region
        )
        self.model_id = settings.bedrock_model_id
        self.embedding_model_id = settings.bedrock_embedding_model

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate text using Bedrock.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        # Build the full prompt based on model type
        if "claude" in self.model_id.lower():
            return await self._generate_claude(prompt, system_prompt, temperature, max_tokens)
        elif "llama" in self.model_id.lower():
            return await self._generate_llama(prompt, system_prompt, temperature, max_tokens)
        elif "titan" in self.model_id.lower():
            return await self._generate_titan(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")

    async def _generate_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Claude models."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            response_body = json.loads(response['body'].read())
            return response_body.get('content', [{}])[0].get('text', '')
        except ClientError as e:
            raise Exception(f"Bedrock Claude error: {e}")

    async def _generate_llama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Llama models."""
        full_prompt = ""
        if system_prompt:
            full_prompt = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]"
        else:
            full_prompt = f"<s>[INST] {prompt} [/INST]"

        request_body = {
            "prompt": full_prompt,
            "max_gen_len": max_tokens,
            "temperature": temperature
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            response_body = json.loads(response['body'].read())
            return response_body.get('generation', '')
        except ClientError as e:
            raise Exception(f"Bedrock Llama error: {e}")

    async def _generate_titan(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Titan models."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        request_body = {
            "inputText": full_prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
                "topP": 0.9
            }
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            response_body = json.loads(response['body'].read())
            return response_body.get('results', [{}])[0].get('outputText', '')
        except ClientError as e:
            raise Exception(f"Bedrock Titan error: {e}")

    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings using Bedrock.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if "titan" in self.embedding_model_id.lower():
            request_body = {
                "inputText": text
            }
        elif "cohere" in self.embedding_model_id.lower():
            request_body = {
                "texts": [text],
                "input_type": "search_document"
            }
        else:
            raise ValueError(f"Unsupported embedding model: {self.embedding_model_id}")

        try:
            response = self.client.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps(request_body)
            )
            response_body = json.loads(response['body'].read())

            if "titan" in self.embedding_model_id.lower():
                return response_body['embedding']
            elif "cohere" in self.embedding_model_id.lower():
                return response_body['embeddings'][0]
        except ClientError as e:
            raise Exception(f"Bedrock embedding error: {e}")

    async def health_check(self) -> bool:
        """Check if Bedrock service is available."""
        try:
            # Try to list available models
            response = self.client.list_foundation_models()
            return True
        except:
            return False