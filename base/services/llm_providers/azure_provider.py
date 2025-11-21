"""
Azure OpenAI provider adapter.

Wraps existing AzureOpenAIService to conform to BaseLLMProvider interface.
"""

import logging
import time
from typing import Dict, List

from openai import OpenAIError

from base.services.openai_service import get_azure_openai_service

from .base_provider import BaseLLMProvider, LLMError, LLMResponse, ModelType

logger = logging.getLogger(__name__)


class AzureProvider(BaseLLMProvider):
    """Azure OpenAI provider adapter."""

    # Pricing per 1M tokens (input / output) - Azure OpenAI o4-mini
    PRICING = {
        ModelType.AZURE_O4_MINI: (6.00, 24.00),  # $6 input, $24 output per 1M tokens
        ModelType.AZURE_GPT4: (
            30.00,
            60.00,
        ),  # $30 input, $60 output per 1M tokens (fallback)
    }

    def __init__(self, model_type: ModelType = ModelType.AZURE_O4_MINI):
        """
        Initialize Azure provider.

        Args:
            model_type: AZURE_O4_MINI or AZURE_GPT4

        Raises:
            LLMError: If Azure OpenAI not configured
        """
        if model_type not in self.PRICING:
            raise ValueError(f"Unsupported model type: {model_type}")

        super().__init__(model_type)

        # Get existing Azure OpenAI service (singleton)
        try:
            self.azure_service = get_azure_openai_service()
            logger.info(
                f"[AZURE] Using deployment: {self.azure_service.chat_deployment}"
            )
        except Exception as e:
            logger.exception(f"[AZURE] Failed to initialize: {str(e)}")
            raise LLMError(
                f"Failed to initialize Azure OpenAI: {str(e)}",
                provider="azure",
                original_error=e,
            )

    def _get_provider_name(self) -> str:
        return "azure"

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text using Azure OpenAI.

        Args:
            messages: Conversation messages [{"role": "user", "content": "..."}]
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (0-2, ignored for o-series)
            **kwargs: Additional parameters (reasoning_effort, etc.)

        Returns:
            LLMResponse with generated text

        Raises:
            LLMError: If API call fails
        """
        start_time = time.time()

        try:
            logger.info(
                f"[AZURE] Generating with {self.model_name}, max_tokens={max_tokens}, temp={temperature}"  # noqa: E501
            )

            # Format messages (pass through, Azure service handles it)
            formatted_messages = self._format_messages(messages)

            # Extract reasoning_effort for o-series models
            reasoning_effort = kwargs.get("reasoning_effort", "low")

            # Call Azure OpenAI service
            response = self.azure_service.chat_completion(
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )

            # Extract data from Azure response
            content = response.get("content", "")
            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Calculate cost
            cost = self.get_cost(input_tokens, output_tokens)

            # Measure latency
            latency = self._measure_latency(start_time)

            logger.info(
                f"[AZURE] Success: {output_tokens} tokens generated, "
                f"cost=${cost:.4f}, latency={latency}s"
            )

            # Build standardized response
            llm_response = LLMResponse(
                content=content,
                model=self.model_name,
                provider=self.provider_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_seconds=latency,
                metadata={
                    "finish_reason": response.get("finish_reason"),
                    "deployment": self.azure_service.chat_deployment,
                    "role": response.get("role"),
                },
            )

            return llm_response

        except OpenAIError as e:
            logger.error(f"[AZURE] OpenAI API error: {str(e)}")
            raise LLMError(
                f"Azure OpenAI error: {str(e)}",
                provider="azure",
                model=self.model_name,
                original_error=e,
            )

        except Exception as e:
            logger.exception(f"[AZURE] Unexpected error: {str(e)}")
            raise LLMError(
                f"Azure generation failed: {str(e)}",
                provider="azure",
                model=self.model_name,
                original_error=e,
            )

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Azure OpenAI usage.

        Pricing:
        - o4-mini: $6 input / $24 output per 1M tokens
        - GPT-4: $30 input / $60 output per 1M tokens

        Args:
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Cost in USD
        """
        input_price, output_price = self.PRICING[self.model_type]

        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return round(input_cost + output_cost, 6)

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format messages for Azure OpenAI (pass-through).

        Azure OpenAI service already handles message formatting,
        including system → developer role conversion for o-series.

        Args:
            messages: Standard message format

        Returns:
            Same format (Azure service handles it internally)
        """
        return messages
