"""
Azure OpenAI Service for AI-powered features.

Provides text embeddings, chat completions, and structured outputs
using Azure OpenAI API.
"""

import logging
from typing import Any, Dict, List, Optional

from decouple import config
from openai import AzureOpenAI
from openai import OpenAIError

logger = logging.getLogger(__name__)


class AzureOpenAIService:
    """Service for interacting with Azure OpenAI API."""

    def __init__(self):
        """Initialize Azure OpenAI client with environment configuration."""
        self.api_key = config("AZURE_OPENAI_API_KEY")
        self.endpoint = config("AZURE_OPENAI_ENDPOINT")
        self.api_version = config("AZURE_OPENAI_API_VERSION", default="2024-02-15-preview")
        self.embedding_deployment = config("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", default="text-embedding-ada-002")
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

    def generate_batch_embeddings(self, texts: List[str], dimensions: int = 1536) -> List[List[float]]:
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
                logger.debug(f"Requesting batch embeddings with {dimensions} dimensions")
            
            response = self.client.embeddings.create(**params)
            embeddings = [item.embedding for item in response.data]
            
            logger.debug(f"Generated {len(embeddings)} embeddings, each with {len(embeddings[0]) if embeddings else 0} dimensions")
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
    ) -> Dict[str, Any]:
        """
        Generate chat completion using GPT model.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            functions: Optional function definitions for function calling
            function_call: Optional function call directive

        Returns:
            Dictionary containing response message and metadata

        Raises:
            OpenAIError: If the API call fails
        """
        try:
            params = {
                "model": self.chat_deployment,
                "messages": messages,
                "temperature": temperature,
            }
            
            # Handle max_tokens parameter based on model type
            # O-series models (o1, o1-mini, o1-preview, o4-mini) use max_completion_tokens
            # Traditional models (gpt-4, gpt-3.5-turbo, gpt-4-turbo) use max_tokens
            # Note: gpt-4o is NOT o-series; it's GPT-4 optimized and uses max_tokens
            if max_tokens:
                model_name = self.chat_deployment.lower()
                
                # Check if it's an o-series model (starts with 'o' followed by digit)
                # Examples: o1, o1-mini, o1-preview, o4-mini
                # NOT: gpt-4o (this is GPT-4 optimized, not o-series)
                is_o_series = (
                    model_name.startswith('o') and 
                    len(model_name) > 1 and 
                    model_name[1].isdigit() and
                    not model_name.startswith('gpt')
                )
                
                if is_o_series:
                    params["max_completion_tokens"] = max_tokens
                    logger.debug(f"[OPENAI] Using max_completion_tokens={max_tokens} for o-series model: {self.chat_deployment}")
                else:
                    params["max_tokens"] = max_tokens
                    logger.debug(f"[OPENAI] Using max_tokens={max_tokens} for model: {self.chat_deployment}")
            
            if functions:
                params["functions"] = functions
            
            if function_call:
                params["function_call"] = function_call
            
            response = self.client.chat.completions.create(**params)
            
            return {
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "function_call": getattr(response.choices[0].message, "function_call", None),
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
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
