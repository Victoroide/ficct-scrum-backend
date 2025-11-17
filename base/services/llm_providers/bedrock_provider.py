"""
AWS Bedrock provider for Llama 4 models.

Supports:
- Llama 4 Maverick (high-quality, higher cost)
- Llama 4 Scout (fast, lower cost)
"""

import json
import logging
import time
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from decouple import config

from .base_provider import BaseLLMProvider, LLMError, LLMResponse, ModelType

logger = logging.getLogger(__name__)


class BedrockProvider(BaseLLMProvider):
    """AWS Bedrock provider for Llama 4 models."""

    # Model IDs in AWS Bedrock
    MODEL_IDS = {
        ModelType.LLAMA4_MAVERICK: "us.meta.llama4-maverick-17b-instruct-v1:0",  # Llama 4 Maverick
        ModelType.LLAMA4_SCOUT: "us.meta.llama4-scout-17b-instruct-v1:0",  # Llama 4 Scout
    }

    # Maximum tokens per model (Bedrock enforced limits)
    MODEL_MAX_TOKENS = {
        ModelType.LLAMA4_MAVERICK: 8192,
        ModelType.LLAMA4_SCOUT: 8192,
    }

    # Pricing per 1M tokens (input / output)
    PRICING = {
        ModelType.LLAMA4_MAVERICK: (
            0.24,
            0.97,
        ),  # $0.24 input, $0.97 output per 1M tokens
        ModelType.LLAMA4_SCOUT: (0.06, 0.24),  # $0.06 input, $0.24 output per 1M tokens
    }

    def __init__(self, model_type: ModelType):
        """
        Initialize Bedrock provider.

        Args:
            model_type: LLAMA4_MAVERICK or LLAMA4_SCOUT

        Raises:
            ValueError: If model_type not supported
            LLMError: If AWS credentials not configured
        """
        if model_type not in self.MODEL_IDS:
            raise ValueError(
                f"Unsupported model type: {model_type}. Must be LLAMA4_MAVERICK or LLAMA4_SCOUT"
            )

        super().__init__(model_type)

        # Initialize Bedrock client (singleton pattern)
        self.client = self._get_bedrock_client()
        self.model_id = self.MODEL_IDS[model_type]

        # Validate correct model ID (catch configuration errors early)
        if model_type == ModelType.LLAMA4_MAVERICK:
            if "llama4-maverick" not in self.model_id:
                raise ValueError(
                    f"Wrong model ID for Llama 4 Maverick: {self.model_id}. "
                    f"Expected: us.meta.llama4-maverick-17b-instruct-v1:0"
                )
        elif model_type == ModelType.LLAMA4_SCOUT:
            if "llama4-scout" not in self.model_id:
                raise ValueError(
                    f"Wrong model ID for Llama 4 Scout: {self.model_id}. "
                    f"Expected: us.meta.llama4-scout-17b-instruct-v1:0"
                )

        logger.info(
            f"[BEDROCK] Initialized {self.model_name} with model ID: {self.model_id}"
        )

    def _get_provider_name(self) -> str:
        return "bedrock"

    def _get_bedrock_client(self):
        """
        Get or create Bedrock client with credentials.

        Returns:
            boto3 Bedrock Runtime client

        Raises:
            LLMError: If credentials not configured
        """
        try:
            # Get AWS credentials from environment
            aws_access_key = config("AWS_ACCESS_KEY_ID", default=None)
            aws_secret_key = config("AWS_SECRET_ACCESS_KEY", default=None)
            aws_region = config("AWS_DEFAULT_REGION", default="us-east-1")

            if not aws_access_key or not aws_secret_key:
                raise LLMError(
                    "AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
                    provider="bedrock",
                )

            # Create Bedrock Runtime client
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )

            logger.debug(f"[BEDROCK] Client created for region: {aws_region}")
            return client

        except Exception as e:
            logger.exception(f"[BEDROCK] Failed to create client: {str(e)}")
            raise LLMError(
                f"Failed to initialize Bedrock client: {str(e)}",
                provider="bedrock",
                original_error=e,
            )

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text using Llama 4 via Bedrock.

        Args:
            messages: Conversation messages [{"role": "user", "content": "..."}]
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (0-1)
            **kwargs: Additional parameters (top_p, etc.)

        Returns:
            LLMResponse with generated text

        Raises:
            LLMError: If API call fails
        """
        start_time = time.time()

        try:
            # Clamp max_tokens to model's limit (prevent ValidationException)
            model_limit = self.MODEL_MAX_TOKENS[self.model_type]
            if max_tokens > model_limit:
                logger.warning(
                    f"[BEDROCK] Requested max_tokens={max_tokens} exceeds model limit={model_limit}. "
                    f"Clamping to {model_limit}"
                )
                max_tokens = model_limit

            logger.info(
                f"[BEDROCK] Generating with {self.model_name}, max_tokens={max_tokens}, temp={temperature}"
            )

            # Format messages in Llama 4 chat template
            formatted_prompt = self._format_messages(messages)

            # Prepare request body
            request_body = {
                "prompt": formatted_prompt,
                "max_gen_len": max_tokens,
                "temperature": temperature,
                "top_p": kwargs.get("top_p", 0.9),
                # NOTE: stop_sequences NOT supported by Bedrock Llama 4 - cleanup with regex instead
            }

            logger.debug(
                f"[BEDROCK] Request body: {json.dumps(request_body, indent=2)[:500]}..."
            )
            logger.debug(f"[BEDROCK] Prompt length: {len(formatted_prompt)} chars")

            # Call Bedrock API
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            logger.debug(
                f"[BEDROCK] Response body: {json.dumps(response_body, indent=2)[:500]}..."
            )

            # Extract generated text
            generated_text = response_body.get("generation", "")

            # FIX: Strip Llama 4 special tokens (defense in depth)
            import re

            generated_text = re.sub(
                r"<\|.*?\|>", "", generated_text
            )  # Remove <|xxx|> tokens
            generated_text = (
                generated_text.strip()
            )  # Remove leading/trailing whitespace

            logger.debug(
                f"[BEDROCK] Cleaned response preview: {generated_text[:200]}..."
            )

            # Extract token usage
            prompt_token_count = response_body.get("prompt_token_count", 0)
            generation_token_count = response_body.get("generation_token_count", 0)

            # Calculate cost
            cost = self.get_cost(prompt_token_count, generation_token_count)

            # Measure latency
            latency = self._measure_latency(start_time)

            logger.info(
                f"[BEDROCK] Success: {generation_token_count} tokens generated, "
                f"cost=${cost:.4f}, latency={latency}s"
            )

            # Build response
            llm_response = LLMResponse(
                content=generated_text,
                model=self.model_name,
                provider=self.provider_name,
                input_tokens=prompt_token_count,
                output_tokens=generation_token_count,
                cost_usd=cost,
                latency_seconds=latency,
                metadata={
                    "stop_reason": response_body.get("stop_reason"),
                    "model_id": self.model_id,
                },
            )

            return llm_response

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"[BEDROCK] AWS ClientError: {error_code} - {error_message}")
            raise LLMError(
                f"Bedrock API error: {error_code} - {error_message}",
                provider="bedrock",
                model=self.model_name,
                original_error=e,
            )

        except json.JSONDecodeError as e:
            logger.exception(f"[BEDROCK] Failed to parse response JSON: {str(e)}")
            raise LLMError(
                f"Failed to parse Bedrock response: {str(e)}",
                provider="bedrock",
                model=self.model_name,
                original_error=e,
            )

        except Exception as e:
            logger.exception(f"[BEDROCK] Unexpected error: {str(e)}")
            raise LLMError(
                f"Bedrock generation failed: {str(e)}",
                provider="bedrock",
                model=self.model_name,
                original_error=e,
            )

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Llama 4 usage.

        Pricing:
        - Maverick: $0.24 input / $0.97 output per 1M tokens
        - Scout: $0.06 input / $0.24 output per 1M tokens

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

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages in Llama 4 chat template format.

        Llama 4 format:
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>

        System message here<|eot_id|>
        <|start_header_id|>user<|end_header_id|>

        User message here<|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>

        Args:
            messages: Standard message format

        Returns:
            Formatted prompt string for Llama 4
        """
        prompt_parts = ["<|begin_of_text|>"]

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # Map 'developer' role to 'system' for Llama (Azure uses 'developer' for o-series)
            if role == "developer":
                role = "system"

            # Add message with Llama 4 template
            prompt_parts.append(
                f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
            )

        # CRITICAL: End with assistant header to trigger generation
        prompt_parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")

        formatted = "".join(prompt_parts)

        logger.debug(f"[BEDROCK] Formatted prompt preview:\n{formatted[:300]}...")

        return formatted
