"""
LLM Proxy Orchestrator.

Routes LLM requests through a fallback chain of providers:
1. Llama 4 Maverick (AWS Bedrock) - Primary, best quality
2. Llama 4 Scout (AWS Bedrock) - Secondary, faster/cheaper
3. Azure OpenAI o4-mini - Final fallback, most expensive

Handles:
- Automatic fallback on errors or empty responses
- Cost tracking per model/provider
- Performance monitoring
- Model-specific prompt optimization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .llm_providers import (
    AzureProvider,
    BaseLLMProvider,
    BedrockProvider,
    LLMError,
    LLMResponse,
    ModelType,
)

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Track LLM usage statistics."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_seconds: float = 0.0
    by_provider: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_response(self, response: LLMResponse, success: bool = True):
        """Record a response in stats."""
        self.total_calls += 1

        if success:
            self.successful_calls += 1
            self.total_cost_usd += response.cost_usd
            self.total_input_tokens += response.input_tokens
            self.total_output_tokens += response.output_tokens
            self.total_latency_seconds += response.latency_seconds

            # Track by provider
            if response.provider not in self.by_provider:
                self.by_provider[response.provider] = {
                    "calls": 0,
                    "cost": 0.0,
                    "tokens": 0,
                }

            self.by_provider[response.provider]["calls"] += 1
            self.by_provider[response.provider]["cost"] += response.cost_usd
            self.by_provider[response.provider]["tokens"] += response.total_tokens
        else:
            self.failed_calls += 1

    def get_average_cost(self) -> float:
        """Get average cost per successful call."""
        if self.successful_calls == 0:
            return 0.0
        return round(self.total_cost_usd / self.successful_calls, 6)

    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        if self.total_calls == 0:
            return 0.0
        return round((self.successful_calls / self.total_calls) * 100, 2)


class LLMProxyService:
    """
    Orchestrates LLM requests with intelligent fallback.

    Usage:
        proxy = LLMProxyService()
        response = proxy.generate(
            task_type='summarize_issue',
            messages=[...],
            fallback_enabled=True
        )
    """

    def __init__(self, enable_fallback: bool = True):
        """
        Initialize proxy with provider chain.

        Args:
            enable_fallback: Enable automatic fallback (default: True)
        """
        self.enable_fallback = enable_fallback
        self.stats = UsageStats()

        # Initialize providers
        self.providers = self._initialize_providers()

        # Define fallback chain (priority order)
        self.fallback_chain = [
            "llama4-maverick",  # Tier 1: Best quality, moderate cost
            "llama4-scout",  # Tier 2: Fast, cheap
            "azure-o4-mini",  # Tier 3: Most expensive, high reliability
        ]

        logger.info(
            f"[LLM PROXY] Initialized with fallback chain: {self.fallback_chain}"
        )
        logger.info(f"[LLM PROXY] Fallback enabled: {self.enable_fallback}")

    def _initialize_providers(self) -> Dict[str, BaseLLMProvider]:
        """
        Initialize all LLM providers.

        Returns:
            Dictionary of provider_key → provider instance
        """
        providers = {}

        try:
            # Try to initialize Llama 4 Maverick (Bedrock)
            providers["llama4-maverick"] = BedrockProvider(ModelType.LLAMA4_MAVERICK)
            logger.info("[LLM PROXY] Llama 4 Maverick ready")
        except Exception as e:
            logger.warning(f"[LLM PROXY] ⚠️ Llama 4 Maverick unavailable: {str(e)}")

        try:
            # Try to initialize Llama 4 Scout (Bedrock)
            providers["llama4-scout"] = BedrockProvider(ModelType.LLAMA4_SCOUT)
            logger.info("[LLM PROXY] Llama 4 Scout ready")
        except Exception as e:
            logger.warning(f"[LLM PROXY] ⚠️ Llama 4 Scout unavailable: {str(e)}")

        try:
            # Initialize Azure OpenAI (always available as fallback)
            providers["azure-o4-mini"] = AzureProvider(ModelType.AZURE_O4_MINI)
            logger.info("[LLM PROXY] Azure O4-Mini ready")
        except Exception as e:
            logger.error(f"[LLM PROXY] ❌ Azure OpenAI unavailable: {str(e)}")
            # Azure is critical - if it fails, we have a problem

        if not providers:
            logger.critical("[LLM PROXY] No LLM providers available!")

        return providers

    def generate(
        self,
        messages: List[Dict[str, str]],
        task_type: str = "general",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        fallback_enabled: Optional[bool] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text with automatic fallback.

        Args:
            messages: Conversation messages [{"role": "user", "content": "..."}]
            task_type: Task identifier (for routing logic, future use)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            fallback_enabled: Override global fallback setting
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse from first successful provider

        Raises:
            LLMError: If all providers fail
        """
        use_fallback = (
            fallback_enabled if fallback_enabled is not None else self.enable_fallback
        )

        logger.info(
            f"[LLM PROXY] Starting generation: task={task_type}, fallback={use_fallback}"
        )

        # Build list of providers to try
        providers_to_try = (
            self.fallback_chain if use_fallback else [self.fallback_chain[0]]
        )

        # Track attempts for logging
        attempts = []

        for provider_key in providers_to_try:
            # Check if provider is available
            if provider_key not in self.providers:
                logger.warning(
                    f"[LLM PROXY] Provider {provider_key} not available, skipping"
                )
                attempts.append(
                    {
                        "provider": provider_key,
                        "status": "unavailable",
                        "error": "Provider not initialized",
                    }
                )
                continue

            provider = self.providers[provider_key]

            try:
                logger.info(f"[LLM PROXY] Attempting with {provider_key}...")

                # Call provider
                response = provider.generate(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

                # Validate response
                if provider._validate_response(response):
                    logger.info(
                        f"[LLM PROXY] SUCCESS with {provider_key}: "
                        f"{response.output_tokens} tokens, ${response.cost_usd:.4f}"
                    )

                    # Record successful response
                    self.stats.add_response(response, success=True)
                    attempts.append(
                        {
                            "provider": provider_key,
                            "status": "success",
                            "tokens": response.total_tokens,
                            "cost": response.cost_usd,
                        }
                    )

                    # Add attempt history to metadata
                    response.metadata["proxy_attempts"] = attempts
                    response.metadata["proxy_task_type"] = task_type

                    return response
                else:
                    # Invalid response (empty, too short, repetitive)
                    logger.warning(
                        f"[LLM PROXY] Invalid response from {provider_key}, trying fallback"
                    )
                    attempts.append(
                        {
                            "provider": provider_key,
                            "status": "invalid_response",
                            "error": "Response failed validation",
                        }
                    )
                    continue

            except LLMError as e:
                # Provider-specific error
                logger.error(f"[LLM PROXY] {provider_key} error: {e.message}")
                attempts.append(
                    {"provider": provider_key, "status": "error", "error": e.message}
                )
                continue

            except Exception as e:
                # Unexpected error
                logger.exception(
                    f"[LLM PROXY] Unexpected error with {provider_key}: {str(e)}"
                )
                attempts.append(
                    {"provider": provider_key, "status": "exception", "error": str(e)}
                )
                continue

        # All providers failed
        self.stats.failed_calls += 1

        error_summary = "\n".join(
            [
                f"  - {attempt['provider']}: {attempt.get('error', attempt.get('status'))}"
                for attempt in attempts
            ]
        )

        logger.error(f"[LLM PROXY] FAILED - All providers failed:\n{error_summary}")

        raise LLMError(
            f"All LLM providers failed. Attempts:\n{error_summary}", provider="proxy"
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.

        Returns:
            Dictionary with usage metrics
        """
        return {
            "total_calls": self.stats.total_calls,
            "successful_calls": self.stats.successful_calls,
            "failed_calls": self.stats.failed_calls,
            "success_rate": self.stats.get_success_rate(),
            "total_cost_usd": round(self.stats.total_cost_usd, 4),
            "average_cost_usd": self.stats.get_average_cost(),
            "total_tokens": self.stats.total_input_tokens
            + self.stats.total_output_tokens,
            "by_provider": self.stats.by_provider,
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.stats = UsageStats()
        logger.info("[LLM PROXY] Statistics reset")


# Global singleton instance
_llm_proxy = None


def get_llm_proxy() -> LLMProxyService:
    """
    Get or create singleton LLM proxy instance.

    Returns:
        LLMProxyService instance
    """
    global _llm_proxy
    if _llm_proxy is None:
        _llm_proxy = LLMProxyService()
    return _llm_proxy
