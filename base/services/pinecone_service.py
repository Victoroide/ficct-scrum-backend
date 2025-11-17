"""
Pinecone Vector Database Service for semantic search and RAG.

Provides vector storage, similarity search, and metadata filtering
using Pinecone API.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from decouple import config
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)


class PineconeService:
    """Service for interacting with Pinecone vector database."""

    def __init__(self):
        """Initialize Pinecone client with environment configuration."""
        self.api_key = config("PINECONE_API_KEY")
        self.environment = config("PINECONE_ENVIRONMENT")
        self.index_name = config("PINECONE_INDEX_NAME", default="ficct-scrum-issues")
        self.dimension = config("PINECONE_DIMENSION", default=1536, cast=int)
        self.metric = config("PINECONE_METRIC", default="cosine")

        self.pc = Pinecone(api_key=self.api_key)
        self._ensure_index_exists()

    def _ensure_index_exists(self):
        """Create index if it doesn't exist."""
        try:
            existing_indexes = self.pc.list_indexes()

            if self.index_name not in [idx.name for idx in existing_indexes]:
                logger.info(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(cloud="aws", region=self.environment),
                )
                logger.info(f"Pinecone index '{self.index_name}' created successfully")

            self.index = self.pc.Index(self.index_name)
        except Exception as e:
            logger.exception(f"Failed to initialize Pinecone index: {str(e)}")
            raise

    def upsert_vector(
        self,
        vector_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        namespace: str = "",
    ) -> bool:
        """
        Insert or update a single vector.

        Args:
            vector_id: Unique identifier for the vector
            vector: Embedding vector (must match index dimension)
            metadata: Optional metadata dictionary
            namespace: Optional namespace for partitioning

        Returns:
            True if successful

        Raises:
            Exception: If upsert fails
        """
        try:
            self.index.upsert(
                vectors=[(vector_id, vector, metadata or {})],
                namespace=namespace,
            )
            logger.debug(f"Upserted vector {vector_id} to Pinecone")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert vector {vector_id}: {str(e)}")
            raise

    def upsert_batch(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        namespace: str = "",
        batch_size: int = 100,
    ) -> int:
        """
        Insert or update multiple vectors in batches.

        Args:
            vectors: List of (id, vector, metadata) tuples
            namespace: Optional namespace for partitioning
            batch_size: Number of vectors per batch

        Returns:
            Number of vectors upserted

        Raises:
            Exception: If batch upsert fails
        """
        try:
            total_upserted = 0

            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                self.index.upsert(vectors=batch, namespace=namespace)
                total_upserted += len(batch)
                logger.debug(
                    f"Upserted batch {i // batch_size + 1}: {len(batch)} vectors"
                )

            logger.info(f"Successfully upserted {total_upserted} vectors to Pinecone")
            return total_upserted
        except Exception as e:
            logger.error(f"Failed to upsert batch: {str(e)}")
            raise

    def query(
        self,
        vector: List[float],
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        namespace: str = "",
        include_metadata: bool = True,
        include_values: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Query for similar vectors.

        Args:
            vector: Query vector
            top_k: Number of results to return
            filter_dict: Optional metadata filter
            namespace: Optional namespace to search within
            include_metadata: Include metadata in results
            include_values: Include vector values in results

        Returns:
            List of matching results with scores and metadata

        Raises:
            Exception: If query fails
        """
        try:
            response = self.index.query(
                vector=vector,
                top_k=top_k,
                filter=filter_dict,
                namespace=namespace,
                include_metadata=include_metadata,
                include_values=include_values,
            )

            results = []
            for match in response.matches:
                result = {
                    "id": match.id,
                    "score": match.score,
                }
                if include_metadata:
                    result["metadata"] = match.metadata
                if include_values:
                    result["values"] = match.values
                results.append(result)

            logger.debug(f"Query returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Failed to query vectors: {str(e)}")
            raise

    def query_by_id(
        self,
        vector_id: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        namespace: str = "",
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Find vectors similar to a specific vector ID.

        Args:
            vector_id: ID of the vector to find similar items for
            top_k: Number of results to return
            filter_dict: Optional metadata filter
            namespace: Optional namespace to search within
            include_metadata: Include metadata in results

        Returns:
            List of similar vectors (excluding the query vector itself)

        Raises:
            Exception: If query fails
        """
        try:
            # Fetch the vector first
            fetch_response = self.index.fetch(ids=[vector_id], namespace=namespace)

            if vector_id not in fetch_response.vectors:
                logger.warning(f"Vector {vector_id} not found in Pinecone")
                return []

            vector = fetch_response.vectors[vector_id].values

            # Query for similar vectors
            results = self.query(
                vector=vector,
                top_k=top_k + 1,  # +1 to account for the query vector itself
                filter_dict=filter_dict,
                namespace=namespace,
                include_metadata=include_metadata,
            )

            # Remove the query vector from results
            results = [r for r in results if r["id"] != vector_id]
            return results[:top_k]
        except Exception as e:
            logger.error(f"Failed to query by ID {vector_id}: {str(e)}")
            raise

    def delete_vector(self, vector_id: str, namespace: str = "") -> bool:
        """
        Delete a vector by ID.

        Args:
            vector_id: ID of the vector to delete
            namespace: Optional namespace

        Returns:
            True if successful

        Raises:
            Exception: If delete fails
        """
        try:
            self.index.delete(ids=[vector_id], namespace=namespace)
            logger.debug(f"Deleted vector {vector_id} from Pinecone")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector {vector_id}: {str(e)}")
            raise

    def delete_by_filter(
        self, filter_dict: Dict[str, Any], namespace: str = ""
    ) -> bool:
        """
        Delete vectors matching a filter.

        Args:
            filter_dict: Metadata filter
            namespace: Optional namespace

        Returns:
            True if successful

        Raises:
            Exception: If delete fails
        """
        try:
            self.index.delete(filter=filter_dict, namespace=namespace)
            logger.info(f"Deleted vectors matching filter: {filter_dict}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete by filter: {str(e)}")
            raise

    def clear_namespace(self, namespace: str = "issues") -> bool:
        """
        Clear all vectors in a namespace.

        Args:
            namespace: Namespace to clear (default: "issues")

        Returns:
            True if successful

        Raises:
            Exception: If clear fails
        """
        try:
            logger.warning(
                f"[PINECONE] Clearing namespace '{namespace}' - ALL VECTORS WILL BE DELETED"
            )
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"[PINECONE] Namespace '{namespace}' cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear namespace '{namespace}': {str(e)}")
            raise

    def get_index_stats(self, namespace: str = "") -> Dict[str, Any]:
        """
        Get statistics about the index.

        Args:
            namespace: Optional namespace

        Returns:
            Dictionary containing index statistics

        Raises:
            Exception: If stats retrieval fails
        """
        try:
            stats = self.index.describe_index_stats()
            return {
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "total_vector_count": stats.total_vector_count,
                "namespaces": stats.namespaces,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {str(e)}")
            raise


# Global instance
_pinecone_service = None


def get_pinecone_service() -> PineconeService:
    """
    Get or create singleton Pinecone service instance.

    Returns:
        PineconeService instance
    """
    global _pinecone_service
    if _pinecone_service is None:
        _pinecone_service = PineconeService()
    return _pinecone_service
