"""FAISS-backed vector store for recipe embeddings. Supports flat (exact) and IVF (approximate) indexes."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import pandas as pd
from loguru import logger

from src.utils.config import settings


class RecipeVectorStore:
    """Manages the FAISS index and associated recipe metadata."""

    def __init__(
        self,
        index_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
    ) -> None:
        self.index_path = index_path or settings.paths.faiss_index
        self.metadata_path = (
            metadata_path or settings.paths.faiss_index.with_suffix(".meta.pkl")
        )
        self.index: Optional[faiss.Index] = None
        self.metadata: Optional[pd.DataFrame] = None

    def build(self, vectors: np.ndarray, metadata: pd.DataFrame) -> None:
        """Build a FAISS index from L2-normalised recipe embedding vectors."""
        n, dim = vectors.shape
        index_type = settings.retrieval.index_type

        logger.info(f"Building FAISS index ({index_type}) for {n:,} vectors of dim {dim}.")

        if index_type == "ivf":
            nlist = settings.retrieval.nlist
            quantiser = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIVFFlat(quantiser, dim, nlist, faiss.METRIC_INNER_PRODUCT)
            logger.info(f"Training IVF index with nlist={nlist}…")
            self.index.train(vectors)
        else:
            # Default: exact inner-product (cosine, since vectors are normalised)
            self.index = faiss.IndexFlatIP(dim)

        self.index.add(vectors)
        self.metadata = metadata.reset_index(drop=True)
        logger.info(f"FAISS index built. Total vectors: {self.index.ntotal:,}")

    def save(self) -> None:
        """Write the index and metadata to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)
        logger.info(f"Index saved to {self.index_path}")
        logger.info(f"Metadata saved to {self.metadata_path}")

    def load(self) -> None:
        """Load the index and metadata from disk."""
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {self.index_path}. "
                "Run the build pipeline first."
            )
        self.index = faiss.read_index(str(self.index_path))
        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)
        logger.info(
            f"Loaded FAISS index ({self.index.ntotal:,} vectors) "
            f"and {len(self.metadata):,} metadata rows."
        )

    def search(self, query_vector: np.ndarray, top_k: int | None = None) -> list[dict]:
        """Return the top-k most similar recipes for a query vector."""
        if self.index is None or self.metadata is None:
            raise RuntimeError("Vector store is not loaded. Call build() or load() first.")

        top_k = top_k or settings.retrieval.top_k
        query_vector = query_vector.astype(np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector[np.newaxis, :]

        scores, indices = self.index.search(query_vector, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue  # FAISS padding for IVF indexes
            if score < settings.retrieval.score_threshold:
                continue
            row = self.metadata.iloc[idx].to_dict()
            row["similarity_score"] = round(float(score), 4)
            results.append(row)

        return results

    def add_recipes(self, new_vectors: np.ndarray, new_metadata: pd.DataFrame) -> None:
        """Add new recipe vectors to an existing index without rebuilding."""
        if self.index is None:
            raise RuntimeError("Index must be built or loaded before adding vectors.")
        self.index.add(new_vectors)
        self.metadata = pd.concat([self.metadata, new_metadata], ignore_index=True)
        logger.info(f"Added {len(new_vectors)} vectors. Total: {self.index.ntotal:,}")

    @property
    def size(self) -> int:
        """Number of vectors stored in the index."""
        return self.index.ntotal if self.index else 0
