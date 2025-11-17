"""
Base LLM Provider interface and shared data structures.

Defines the contract that all LLM providers must implement.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported LLM model types."""

    LLAMA4_MAVERICK = "llama4-maverick"
    LLAMA4_SCOUT = "llama4-scout"
    AZURE_O4_MINI = "azure-o4-mini"
    AZURE_GPT4 = "azure-gpt4"


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    def __str__(self) -> str:
        return (
            f"LLMResponse(provider={self.provider}, model={self.model}, "
            f"tokens={self.total_tokens}, cost=${self.cost_usd:.4f}, "
            f"latency={self.latency_seconds:.2f}s)"
        )


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = None,
        model: str = None,
        original_error: Exception = None,
    ):
        self.message = message
        self.provider = provider
        self.model = model
        self.original_error = original_error
        super().__init__(self.message)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement:
    - generate(): Text generation
    - get_cost(): Cost calculation
    - _format_messages(): Provider-specific message formatting
    """

    def __init__(self, model_type: ModelType):
        """
        Initialize provider with model type.

        Args:
            model_type: Model enum identifying which model to use
        """
        self.model_type = model_type
        self.provider_name = self._get_provider_name()
        self.model_name = model_type.value
        logger.info(
            f"[{self.provider_name.upper()}] Initialized provider for model: {self.model_name}"
        )

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return provider name (e.g., 'bedrock', 'azure')."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with generated text and metadata

        Raises:
            LLMError: If generation fails
        """
        pass

    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for given token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pass

    @abstractmethod
    def _format_messages(self, messages: List[Dict[str, str]]) -> Any:
        """
        Format messages for provider-specific API format.

        Args:
            messages: Standard message format [{"role": "user", "content": "..."}]

        Returns:
            Provider-specific message format
        """
        pass

    def _validate_response(self, response: LLMResponse) -> bool:
        """
        Validate response quality.

        Args:
            response: LLMResponse to validate

        Returns:
            True if response is valid, False otherwise
        """
        # Check for empty content
        if not response.content or len(response.content.strip()) == 0:
            logger.warning(f"[{self.provider_name.upper()}] Empty response detected")
            return False

        # Check for minimum length (avoid empty or single-char responses)
        # Note: Valid short responses like "One", "Two", "Three" are 3-5 chars
        if len(response.content.strip()) < 3:
            logger.warning(
                f"[{self.provider_name.upper()}] Response too short: {len(response.content)} chars"
            )
            return False

        # Check for repetitive patterns (model stuck in loop)
        words = response.content.split()
        if len(words) > 10:
            # Check if same word repeated many times
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            max_repetition = max(word_counts.values())
            if max_repetition > len(words) * 0.5:  # More than 50% repetition
                logger.warning(
                    f"[{self.provider_name.upper()}] Repetitive content detected"
                )
                return False

        return True

    def _measure_latency(self, start_time: float) -> float:
        """Calculate latency in seconds."""
        return round(time.time() - start_time, 3)
