"""High-level retrieval interface: encodes query → FAISS search → post-processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from src.embedding.embedder import RecipeEmbedder
from src.embedding.vector_store import RecipeVectorStore
from src.preprocessing.ingredient_parser import (
    match_ingredients,
    get_substitutions,
    normalise_ingredient_list,
)
from src.utils.config import settings


@dataclass
class RetrievedRecipe:
    """A single retrieved recipe with scores and ingredient match details."""
    id: str
    title: str
    ingredients: list[str]
    instructions: str
    tags: list[str] = field(default_factory=list)
    similarity_score: float = 0.0
    matched_ingredients: list[str] = field(default_factory=list)
    missing_ingredients: list[str] = field(default_factory=list)
    ingredient_score: float = 0.0
    combined_score: float = 0.0
    substitutions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "ingredients": self.ingredients,
            "instructions": self.instructions,
            "tags": self.tags,
            "similarity_score": self.similarity_score,
            "matched_ingredients": self.matched_ingredients,
            "missing_ingredients": self.missing_ingredients,
            "ingredient_score": self.ingredient_score,
            "combined_score": self.combined_score,
            "substitutions": self.substitutions,
        }


class RecipeRetriever:
    """Orchestrates embedding → vector search → post-processing."""

    # Final score = 60% similarity + 40% ingredient coverage
    SIMILARITY_WEIGHT = 0.6
    INGREDIENT_WEIGHT = 0.4

    def __init__(
        self,
        embedder: Optional[RecipeEmbedder] = None,
        vector_store: Optional[RecipeVectorStore] = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._loaded = False

    def load(self) -> None:
        """Initialise the embedder and load the FAISS index. Safe to call multiple times."""
        if self._loaded:
            return
        if self._embedder is None:
            self._embedder = RecipeEmbedder()
        if self._vector_store is None:
            self._vector_store = RecipeVectorStore()
            self._vector_store.load()
        self._loaded = True
        logger.info("RecipeRetriever ready.")

    def retrieve(
        self,
        ingredients: list[str],
        top_k: int | None = None,
        context: str = "",
    ) -> list[RetrievedRecipe]:
        """Retrieve and rank the top-k recipes for a given ingredient list."""
        if not self._loaded:
            self.load()

        top_k = top_k or settings.retrieval.top_k

        logger.debug(f"Encoding query for ingredients: {ingredients}")
        query_vec = self._embedder.encode_query(ingredients, extra_context=context)

        # Fetch 3x candidates so we have room to re-rank
        candidate_k = min(top_k * 3, self._vector_store.size or top_k)
        raw_results = self._vector_store.search(query_vec, top_k=candidate_k)
        logger.debug(f"FAISS returned {len(raw_results)} candidates.")

        enriched: list[RetrievedRecipe] = []
        for raw in raw_results:
            recipe_ings = raw.get("ingredients", [])
            if isinstance(recipe_ings, str):
                import ast
                try:
                    recipe_ings = ast.literal_eval(recipe_ings)
                except Exception:
                    recipe_ings = [recipe_ings]

            match_result = match_ingredients(ingredients, recipe_ings)
            subs = get_substitutions(match_result["missing"])

            sim_score = raw.get("similarity_score", 0.0)
            ing_score = match_result["score"]
            combined = self.SIMILARITY_WEIGHT * sim_score + self.INGREDIENT_WEIGHT * ing_score

            enriched.append(
                RetrievedRecipe(
                    id=str(raw.get("id", "")),
                    title=str(raw.get("clean_title") or raw.get("title", "")),
                    ingredients=recipe_ings if isinstance(recipe_ings, list) else [],
                    instructions=str(raw.get("clean_instructions") or raw.get("instructions", "")),
                    tags=raw.get("clean_tags") or raw.get("tags") or [],
                    similarity_score=round(sim_score, 4),
                    matched_ingredients=match_result["matched"],
                    missing_ingredients=match_result["missing"],
                    ingredient_score=round(ing_score, 4),
                    combined_score=round(combined, 4),
                    substitutions=subs,
                )
            )

        enriched.sort(key=lambda r: r.combined_score, reverse=True)
        logger.info(f"Returning top {min(top_k, len(enriched))} recipes.")
        return enriched[:top_k]

    @property
    def store_size(self) -> int:
        """Number of recipes indexed."""
        if self._vector_store:
            return self._vector_store.size
        return 0
