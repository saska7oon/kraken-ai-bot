"""
OpenRouter API Client for AI Orchestrator

Supports multiple models with fallback, streaming, and cost tracking.
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


@dataclass
class ChatMessage:
    """Chat message format."""
    role: str  # system, user, assistant
    content: str


@dataclass
class ChatCompletionRequest:
    """Chat completion request."""
    model: str
    messages: List[ChatMessage]
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False
    response_format: Optional[Dict[str, str]] = None


@dataclass
class ChatCompletionResponse:
    """Chat completion response."""
    id: str
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    created: int


@dataclass
class ModelUsage:
    """Track model usage for cost monitoring."""
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    last_used: datetime = field(default_factory=datetime.now)


class OpenRouterClient:
    """
    Async OpenRouter API client with model fallback and usage tracking.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        default_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free",
        fallback_models: Optional[List[str]] = None,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.fallback_models = fallback_models or [
            "deepseek/deepseek-chat",
            "google/gemini-flash-1.5",
            "anthropic/claude-3.5-haiku",
        ]
        self.timeout = ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.usage_stats: Dict[str, ModelUsage] = {}
        self._model_configs: Dict[str, ModelConfig] = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/kraken-ai-bot",
                "X-Title": "Kraken AI Trading Bot",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _ensure_session(self):
        """Ensure session exists."""
        if self.session is None or self.session.closed:
            await self.__aenter__()

    def _get_model_config(self, model: str) -> ModelConfig:
        """Get or create model configuration."""
        if model not in self._model_configs:
            self._model_configs[model] = ModelConfig(name=model)
        return self._model_configs[model]

    def _update_usage(self, model: str, usage: Dict[str, int]):
        """Update usage statistics."""
        if model not in self.usage_stats:
            self.usage_stats[model] = ModelUsage(model=model)
        stats = self.usage_stats[model]
        stats.prompt_tokens += usage.get("prompt_tokens", 0)
        stats.completion_tokens += usage.get("completion_tokens", 0)
        stats.total_tokens += usage.get("total_tokens", 0)
        stats.requests += 1
        stats.last_used = datetime.now()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        response_format: Optional[Dict[str, str]] = None,
        use_fallback: bool = True,
    ) -> ChatCompletionResponse:
        """
        Send chat completion request with automatic fallback.
        """
        await self._ensure_session()

        model = model or self.default_model
        models_to_try = [model]
        if use_fallback:
            models_to_try.extend([m for m in self.fallback_models if m != model])

        last_error = None

        for attempt_model in models_to_try:
            for retry in range(self.max_retries):
                try:
                    payload = {
                        "model": attempt_model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": stream,
                    }
                    if response_format:
                        payload["response_format"] = response_format

                    async with self.session.post(
                        f"{self.BASE_URL}/chat/completions",
                        json=payload,
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._update_usage(attempt_model, data.get("usage", {}))
                            return ChatCompletionResponse(**data)
                        elif response.status == 429:
                            # Rate limited - wait and retry
                            wait_time = 2 ** retry
                            logger.warning(f"Rate limited on {attempt_model}, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        elif response.status >= 500:
                            # Server error - retry
                            wait_time = 2 ** retry
                            logger.warning(f"Server error {response.status} on {attempt_model}, retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Client error - don't retry, try fallback
                            error_text = await response.text()
                            logger.error(f"API error {response.status} on {attempt_model}: {error_text}")
                            last_error = f"API {response.status}: {error_text}"
                            break

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on {attempt_model} (retry {retry + 1}/{self.max_retries})")
                    last_error = "Timeout"
                except Exception as e:
                    logger.error(f"Error calling {attempt_model}: {e}")
                    last_error = str(e)

            # If we get here, all retries failed for this model
            logger.warning(f"All retries failed for {attempt_model}, trying fallback")
            continue

        # All models failed
        raise Exception(f"All models failed. Last error: {last_error}")

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion.
        """
        await self._ensure_session()

        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with self.session.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Stream API error {response.status}: {error_text}")

            async for line in response.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def get_usage_stats(self) -> Dict[str, ModelUsage]:
        """Get usage statistics for all models."""
        return self.usage_stats

    def get_total_cost_estimate(self) -> float:
        """
        Estimate total cost based on usage.
        Note: OpenRouter pricing varies by model.
        This is a rough estimate for free models.
        """
        # Free models have $0 cost
        return 0.0

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from OpenRouter."""
        await self._ensure_session()
        async with self.session.get(f"{self.BASE_URL}/models") as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            return []

    async def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model."""
        models = await self.list_models()
        for m in models:
            if m.get("id") == model:
                return m
        return None