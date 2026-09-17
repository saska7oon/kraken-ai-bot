"""
OpenRouter API Client for AI Orchestrator

Supports multiple models with fallback, streaming, and cost tracking.
"""

import os
import json
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


class AIBudgetExhausted(Exception):
    """
    Raised when the daily AI request budget is spent.

    This is an expected, non-fatal condition: the deterministic trading strategy
    is entirely unaffected by AI availability.
    """


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
    Async OpenRouter API client with model fallback, usage tracking and a daily
    request budget.

    Budget note: the default configuration uses a FREE OpenRouter model with a
    hard cap of 200 requests/day. The bot's plugins can easily exceed that, and
    a mid-run 429 used to look like a silent failure. This client therefore
    tracks requests per UTC day and refuses to spend more, raising
    ``AIBudgetExhausted`` so callers can degrade gracefully instead of retrying
    into the wall.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        default_model: str = "",
        fallback_models: Optional[List[str]] = None,
        timeout: int = 60,
        max_retries: int = 3,
        daily_request_budget: int = 180,
    ):
        self.api_key = api_key
        self.default_model = default_model
        # No invented defaults: whatever is listed in ai_orchestrator.yaml wins.
        # Silently defaulting to paid models could charge the operator money.
        self.fallback_models = fallback_models or []
        self.timeout = ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.usage_stats: Dict[str, ModelUsage] = {}
        self._model_configs: Dict[str, ModelConfig] = {}

        # Daily budget accounting. 180 leaves headroom under the free 200/day cap.
        self.daily_request_budget = daily_request_budget
        self._requests_today = 0
        self._budget_day = datetime.now(timezone.utc).date()
        self._budget_exhausted_logged = False

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
        await self.close()

    async def close(self):
        """Close the HTTP session. Safe to call more than once."""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    # ------------------------------------------------------------------ budget
    def _roll_budget_day(self) -> None:
        """Reset the request counter when the UTC day changes."""
        today = datetime.now(timezone.utc).date()
        if today != self._budget_day:
            logger.info(
                "OpenRouter daily budget reset (previous day used %d requests)",
                self._requests_today,
            )
            self._budget_day = today
            self._requests_today = 0
            self._budget_exhausted_logged = False

    def budget_status(self) -> Dict[str, Any]:
        """Current budget consumption, for reporting to the operator."""
        self._roll_budget_day()
        return {
            "requests_today": self._requests_today,
            "daily_budget": self.daily_request_budget,
            "remaining": max(0, self.daily_request_budget - self._requests_today),
            "exhausted": self._requests_today >= self.daily_request_budget,
        }

    def _budget_exhausted_reason(self) -> Optional[str]:
        """Return an explanation if no budget remains, else None."""
        self._roll_budget_day()
        if self._requests_today < self.daily_request_budget:
            return None
        if not self._budget_exhausted_logged:
            logger.warning(
                "OpenRouter daily request budget exhausted (%d/%d). AI features are "
                "paused until 00:00 UTC. Trading is unaffected - the deterministic "
                "strategy keeps running.",
                self._requests_today,
                self.daily_request_budget,
            )
            self._budget_exhausted_logged = True
        return (
            f"Daily AI request budget exhausted "
            f"({self._requests_today}/{self.daily_request_budget}). "
            f"Resets at 00:00 UTC."
        )

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

        Raises ``AIBudgetExhausted`` when the daily request budget is spent, so
        callers can degrade gracefully rather than hammering a rate limit.
        """
        await self._ensure_session()

        exhausted = self._budget_exhausted_reason()
        if exhausted:
            raise AIBudgetExhausted(exhausted)

        model = model or self.default_model
        if not model:
            raise AIBudgetExhausted(
                "No AI model is configured. Set 'model' in ai_orchestrator.yaml."
            )

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
                            self._requests_today += 1
                            self._update_usage(attempt_model, data.get("usage", {}))
                            # Build explicitly rather than ChatCompletionResponse(**data).
                            #
                            # The provider's payload carries keys this dataclass
                            # does not model - "object" on every response, plus
                            # "system_fingerprint" and anything new it adds later -
                            # and splatting it raised
                            #   TypeError: ChatCompletionResponse.__init__() got an
                            #   unexpected keyword argument 'object'
                            # on EVERY call. The AI narration never once succeeded:
                            # each request burned its retries, fell through to the
                            # fallback model, failed there too, and the explainer
                            # quietly served the deterministic digest instead. The
                            # failure was invisible in the UI because a digest was
                            # still produced - it simply was not the AI's.
                            #
                            # Naming the fields means an unknown key is ignored
                            # instead of fatal, which is the right default for a
                            # third-party API that adds fields without notice.
                            return ChatCompletionResponse(
                                id=data.get("id", ""),
                                model=data.get("model", attempt_model),
                                choices=data.get("choices") or [],
                                usage=data.get("usage") or {},
                                created=data.get("created", 0),
                            )
                        elif response.status == 429:
                            # Rate limited. Respect Retry-After when present, then
                            # fall back to exponential backoff with jitter so two
                            # plugins hitting the limit together do not sync up.
                            retry_after = response.headers.get("Retry-After")
                            try:
                                wait_time = float(retry_after) if retry_after else 2 ** retry
                            except ValueError:
                                wait_time = 2 ** retry
                            wait_time = min(wait_time, 60) + random.uniform(0, 1)
                            logger.warning(
                                "Rate limited on %s, waiting %.1fs (attempt %d/%d)",
                                attempt_model,
                                wait_time,
                                retry + 1,
                                self.max_retries,
                            )
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