"""
Data loader service for loading RAG index data from local files or S3.
"""

import os
import json
import pickle
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from abc import ABC, abstractmethod

from ..config import settings, is_production


class DataLoader(ABC):
    """Abstract base class for data loaders."""

    @abstractmethod
    async def load_chunks(self) -> list:
        """Load chunks data."""
        pass

    @abstractmethod
    async def load_embeddings(self) -> np.ndarray:
        """Load embeddings numpy array."""
        pass

    @abstractmethod
    async def load_metadata(self) -> Dict[str, Any]:
        """Load metadata."""
        pass

    @abstractmethod
    async def load_bm25_index(self) -> Any:
        """Load BM25 index."""
        pass

    @abstractmethod
    async def load_index_summary(self) -> Dict[str, Any]:
        """Load index summary."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if data source is available."""
        pass


class LocalDataLoader(DataLoader):
    """Load data from local filesystem."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or settings.data_dir)

    async def load_chunks(self) -> list:
        """Load chunks from local JSON file."""
        chunks_path = self.data_dir / settings.chunks_file
        if not chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

        with open(chunks_path, "r") as f:
            return json.load(f)

    async def load_embeddings(self) -> np.ndarray:
        """Load embeddings from local numpy file."""
        embeddings_path = self.data_dir / settings.embeddings_file
        if not embeddings_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {embeddings_path}")

        return np.load(embeddings_path)

    async def load_metadata(self) -> Dict[str, Any]:
        """Load metadata from local JSON file."""
        metadata_path = self.data_dir / settings.metadata_file
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        with open(metadata_path, "r") as f:
            return json.load(f)

    async def load_bm25_index(self) -> Any:
        """Load BM25 index from local pickle file."""
        bm25_path = self.data_dir / settings.bm25_file
        if not bm25_path.exists():
            raise FileNotFoundError(f"BM25 index not found: {bm25_path}")

        # Import BM25 here to avoid circular imports
        from rag.bm25 import BM25
        return BM25.load(str(bm25_path))

    async def load_index_summary(self) -> Dict[str, Any]:
        """Load index summary from local JSON file."""
        summary_path = self.data_dir / "index_summary.json"
        if not summary_path.exists():
            # Return default if not found
            return {
                "num_posts": 0,
                "num_chunks": 0,
                "last_updated": None
            }

        with open(summary_path, "r") as f:
            return json.load(f)

    async def health_check(self) -> bool:
        """Check if all required data files exist."""
        required_files = [
            self.data_dir / settings.chunks_file,
            self.data_dir / settings.embeddings_file,
            self.data_dir / settings.bm25_file
        ]
        return all(f.exists() for f in required_files)


class S3DataLoader(DataLoader):
    """Load data from S3 bucket."""

    def __init__(self, bucket_name: Optional[str] = None):
        import boto3
        self.bucket_name = bucket_name or settings.s3_bucket
        if not self.bucket_name:
            raise ValueError("S3 bucket name not configured")

        self.s3_client = boto3.client("s3", region_name=settings.aws_region)
        self.temp_dir = Path(tempfile.gettempdir()) / "rag_data"
        self.temp_dir.mkdir(exist_ok=True)
        self._cache = {}

    async def _download_file(self, s3_key: str, local_path: Path) -> Path:
        """Download a file from S3 to local temp directory."""
        # Check if already cached
        if local_path.exists():
            print(f"Using cached file: {local_path}")
            return local_path

        print(f"Downloading from S3: {s3_key}")
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, str(local_path))
            return local_path
        except Exception as e:
            raise FileNotFoundError(f"Failed to download {s3_key} from S3: {e}")

    async def load_chunks(self) -> list:
        """Load chunks from S3."""
        local_path = self.temp_dir / settings.chunks_file
        await self._download_file(settings.chunks_file, local_path)

        with open(local_path, "r") as f:
            return json.load(f)

    async def load_embeddings(self) -> np.ndarray:
        """Load embeddings from S3."""
        local_path = self.temp_dir / settings.embeddings_file
        await self._download_file(settings.embeddings_file, local_path)

        return np.load(local_path)

    async def load_metadata(self) -> Dict[str, Any]:
        """Load metadata from S3."""
        local_path = self.temp_dir / settings.metadata_file
        await self._download_file(settings.metadata_file, local_path)

        with open(local_path, "r") as f:
            return json.load(f)

    async def load_bm25_index(self) -> Any:
        """Load BM25 index from S3."""
        local_path = self.temp_dir / settings.bm25_file
        await self._download_file(settings.bm25_file, local_path)

        # Import BM25 here to avoid circular imports
        from rag.bm25 import BM25
        return BM25.load(str(local_path))

    async def load_index_summary(self) -> Dict[str, Any]:
        """Load index summary from S3."""
        local_path = self.temp_dir / "index_summary.json"
        try:
            await self._download_file("index_summary.json", local_path)
            with open(local_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default if not found
            return {
                "num_posts": 0,
                "num_chunks": 0,
                "last_updated": None
            }

    async def health_check(self) -> bool:
        """Check if S3 bucket is accessible and contains required files."""
        try:
            # Check if bucket exists and we have access
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )

            # Check if required files exist
            required_files = [
                settings.chunks_file,
                settings.embeddings_file,
                settings.bm25_file
            ]

            for file_key in required_files:
                try:
                    self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
                except:
                    return False

            return True
        except Exception as e:
            print(f"S3 health check failed: {e}")
            return False


class DataLoaderFactory:
    """Factory for creating appropriate data loader based on configuration."""

    @staticmethod
    def create_loader() -> DataLoader:
        """Create data loader based on environment and configuration."""
        data_source = os.getenv("DATA_SOURCE", "local")

        if data_source == "s3" or (is_production() and settings.s3_bucket):
            print("Using S3 data loader")
            return S3DataLoader()
        else:
            print("Using local data loader")
            return LocalDataLoader()


# Convenience function for getting a loader
def get_data_loader() -> DataLoader:
    """Get the appropriate data loader for the current environment."""
    return DataLoaderFactory.create_loader()