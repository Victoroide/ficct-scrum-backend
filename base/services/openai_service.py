"""
Azure OpenAI Service for AI-powered features.

Provides text embeddings, chat completions, and structured outputs
using Azure OpenAI API.
"""

import logging
from typing import Any, Dict, List, Optional

from decouple import config
from openai import AzureOpenAI, OpenAIError

logger = logging.getLogger(__name__)


class AzureOpenAIService:
    """Service for interacting with Azure OpenAI API."""

    def __init__(self):
        """Initialize Azure OpenAI client with environment configuration."""
        self.api_key = config("AZURE_OPENAI_API_KEY")
        self.endpoint = config("AZURE_OPENAI_ENDPOINT")
        self.api_version = config(
            "AZURE_OPENAI_API_VERSION", default="2024-02-15-preview"
        )
        self.embedding_deployment = config(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", default="text-embedding-ada-002"
        )
        self.chat_deployment = config("AZURE_OPENAI_CHAT_DEPLOYMENT", default="gpt-4")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
        )

    def generate_embedding(self, text: str, dimensions: int = 1536) -> List[float]:
        """
        Generate embedding vector for given text.

        Args:
            text: Input text to embed
            dimensions: Embedding dimensions (default 1536)
                       - text-embedding-3-small supports 512 or 1536
                       - text-embedding-3-large supports 256, 1024, or 3072
                       - text-embedding-ada-002 is always 1536 (parameter ignored)

        Returns:
            List of floats representing the embedding vector

        Raises:
            OpenAIError: If the API call fails
        """
        try:
            # Build parameters
            params = {
                "input": text,
                "model": self.embedding_deployment,
            }

            # Add dimensions parameter for newer models (v3 models support it)
            # Ada-002 doesn't support this parameter but always returns 1536
            if "text-embedding-3" in self.embedding_deployment:
                params["dimensions"] = dimensions
                logger.debug(f"Requesting embedding with {dimensions} dimensions")

            response = self.client.embeddings.create(**params)
            embedding = response.data[0].embedding

            logger.debug(f"Generated embedding: {len(embedding)} dimensions")
            return embedding

        except OpenAIError as e:
            logger.error(f"Azure OpenAI embedding error: {str(e)}")
            raise
        except Exception as e:
            logger.exception("Unexpected error generating embedding")
            raise OpenAIError(f"Failed to generate embedding: {str(e)}")

    def generate_batch_embeddings(
        self, texts: List[str], dimensions: int = 1536
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of input texts
            dimensions: Embedding dimensions (default 1536)

        Returns:
            List of embedding vectors

        Raises:
            OpenAIError: If the API call fails
        """
        try:
            # Build parameters
            params = {
                "input": texts,
                "model": self.embedding_deployment,
            }

            # Add dimensions parameter for newer models
            if "text-embedding-3" in self.embedding_deployment:
                params["dimensions"] = dimensions
                logger.debug(
                    f"Requesting batch embeddings with {dimensions} dimensions"
                )

            response = self.client.embeddings.create(**params)
            embeddings = [item.embedding for item in response.data]

            logger.debug(
                f"Generated {len(embeddings)} embeddings, each with {len(embeddings[0]) if embeddings else 0} dimensions"
            )
            return embeddings

        except OpenAIError as e:
            logger.error(f"Azure OpenAI batch embedding error: {str(e)}")
            raise
        except Exception as e:
            logger.exception("Unexpected error generating batch embeddings")
            raise OpenAIError(f"Failed to generate batch embeddings: {str(e)}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate chat completion using GPT model.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-2) - ignored for o-series models
            max_tokens: Maximum tokens in response
            functions: Optional function definitions for function calling - ignored for o-series
            function_call: Optional function call directive - ignored for o-series
            reasoning_effort: Reasoning depth for o-series models ("low"|"medium"|"high")

        Returns:
            Dictionary containing response message and metadata

        Raises:
            OpenAIError: If the API call fails

        Note:
            O-series models (o1, o1-mini, o4-mini) have strict parameter restrictions:
            - Do NOT support: temperature, top_p, functions, penalties
            - REQUIRE: max_completion_tokens instead of max_tokens
            - SUPPORT: reasoning_effort for controlling reasoning depth
            - Convert 'system' role to 'developer' role automatically
        """
        try:
            model_name = self.chat_deployment.lower()

            # Detect o-series reasoning models
            # Examples: o1, o1-mini, o1-preview, o4-mini
            # NOT: gpt-4o (GPT-4 optimized, not o-series)
            is_o_series = (
                model_name.startswith("o")
                and len(model_name) > 1
                and model_name[1].isdigit()
                and not model_name.startswith("gpt")
            )

            # Prepare messages with role conversion for o-series
            processed_messages = messages.copy()
            if is_o_series:
                # Convert 'system' role to 'developer' role for o-series models
                processed_messages = [
                    {**msg, "role": "developer"} if msg.get("role") == "system" else msg
                    for msg in messages
                ]
                logger.debug(
                    f"[OPENAI] Converted system roles to developer for o-series model"
                )

            # Build base parameters
            params = {
                "model": self.chat_deployment,
                "messages": processed_messages,
            }

            # O-SERIES MODELS: Use restricted parameter set
            if is_o_series:
                logger.info(
                    f"[OPENAI] Detected o-series model: {self.chat_deployment}, using restricted parameters"
                )

                # REQUIRED: max_completion_tokens (not max_tokens)
                # Default: 16000 for o-series (increased from 4096 to prevent token exhaustion)
                # Reasoning models need high budgets: reasoning + output tokens
                token_limit = max_tokens if max_tokens else 16000
                params["max_completion_tokens"] = token_limit
                logger.debug(f"[OPENAI] max_completion_tokens={token_limit}")

                # OPTIONAL: reasoning_effort controls reasoning depth and token usage
                # Values: "low" (faster, less reasoning), "medium" (balanced), "high" (thorough)
                # Default: "low" for RAG queries to maximize output space
                effort = reasoning_effort if reasoning_effort else "low"
                params["reasoning_effort"] = effort
                logger.debug(f"[OPENAI] reasoning_effort={effort}")

                # EXCLUDED PARAMETERS (cause 400 Bad Request):
                # - temperature, top_p, presence_penalty, frequency_penalty
                # - functions, function_call
                # - logprobs, top_logprobs, logit_bias
                logger.debug(
                    f"[OPENAI] Excluded unsupported params: temperature, functions, penalties"
                )

            # TRADITIONAL MODELS: Use standard parameters
            else:
                logger.debug(
                    f"[OPENAI] Traditional model: {self.chat_deployment}, using standard parameters"
                )

                # Include temperature for traditional models
                params["temperature"] = temperature
                logger.debug(f"[OPENAI] temperature={temperature}")

                # Include max_tokens if provided
                if max_tokens:
                    params["max_tokens"] = max_tokens
                    logger.debug(f"[OPENAI] max_tokens={max_tokens}")

                # Include function calling parameters if provided
                if functions:
                    params["functions"] = functions
                    logger.debug(
                        f"[OPENAI] Added {len(functions)} function definitions"
                    )

                if function_call:
                    params["function_call"] = function_call
                    logger.debug(f"[OPENAI] function_call={function_call}")

            # Log final request
            logger.info(
                f"[OPENAI] Calling chat completion with {len(processed_messages)} messages"
            )

            response = self.client.chat.completions.create(**params)

            # Log completion details (especially important for o-series debugging)
            finish_reason = response.choices[0].finish_reason
            usage = response.usage
            logger.info(
                f"[OPENAI] Completion finished: reason={finish_reason}, tokens={usage.total_tokens}"
            )

            # For o-series models, log reasoning/output token breakdown
            if is_o_series and hasattr(usage, "completion_tokens_details"):
                details = usage.completion_tokens_details
                if hasattr(details, "reasoning_tokens"):
                    logger.debug(
                        f"[OPENAI] Token breakdown: "
                        f"reasoning={details.reasoning_tokens}, "
                        f"output={getattr(details, 'accepted_prediction_tokens', 0) or usage.completion_tokens - details.reasoning_tokens}"
                    )

            # Warning if budget exhausted (empty response likely)
            if finish_reason == "length":
                logger.warning(
                    f"[OPENAI] Token budget exhausted (finish_reason='length'). "
                    f"Response may be truncated or empty. Consider increasing max_completion_tokens."
                )

            return {
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "function_call": getattr(
                    response.choices[0].message, "function_call", None
                ),
                "finish_reason": finish_reason,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
            }
        except OpenAIError as e:
            logger.error(f"Azure OpenAI chat completion error: {str(e)}")
            raise
        except Exception as e:
            logger.exception("Unexpected error in chat completion")
            raise OpenAIError(f"Failed to generate chat completion: {str(e)}")

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate a concise summary of the given text.

        Args:
            text: Text to summarize
            max_length: Maximum length of summary in words

        Returns:
            Summary text

        Raises:
            OpenAIError: If the API call fails
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that creates concise summaries. "
                    f"Summarize the following text in no more than {max_length} words."
                ),
            },
            {"role": "user", "content": text},
        ]

        try:
            response = self.chat_completion(messages, temperature=0.3)
            return response["content"]
        except OpenAIError:
            raise
        except Exception as e:
            logger.exception("Unexpected error generating summary")
            raise OpenAIError(f"Failed to generate summary: {str(e)}")

    def extract_structured_data(
        self, text: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured data from text using function calling.

        Args:
            text: Text to extract data from
            schema: JSON schema defining the expected structure

        Returns:
            Extracted structured data

        Raises:
            OpenAIError: If the API call fails
        """
        function_def = {
            "name": "extract_data",
            "description": "Extract structured data from the text",
            "parameters": schema,
        }

        messages = [
            {
                "role": "system",
                "content": "You are a data extraction assistant. Extract the requested information from the text.",
            },
            {"role": "user", "content": text},
        ]

        try:
            response = self.chat_completion(
                messages,
                functions=[function_def],
                function_call={"name": "extract_data"},
                temperature=0.0,
            )

            if response.get("function_call"):
                import json

                return json.loads(response["function_call"].arguments)
            else:
                logger.warning("No function call in response")
                return {}
        except OpenAIError:
            raise
        except Exception as e:
            logger.exception("Unexpected error extracting structured data")
            raise OpenAIError(f"Failed to extract structured data: {str(e)}")


# Global instance
_azure_openai_service = None


def get_azure_openai_service() -> AzureOpenAIService:
    """
    Get or create singleton Azure OpenAI service instance.

    Returns:
        AzureOpenAIService instance
    """
    global _azure_openai_service
    if _azure_openai_service is None:
        _azure_openai_service = AzureOpenAIService()
    return _azure_openai_service
