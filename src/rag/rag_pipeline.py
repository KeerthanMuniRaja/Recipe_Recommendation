"""
src/rag/rag_pipeline.py
────────────────────────────────────────────────────────
RAG (Retrieval-Augmented Generation) pipeline.

Flow
────
  user ingredients
        │
        ▼
  RecipeRetriever.retrieve()    ← FAISS similarity search
        │
        ▼
  format_recipe_context()       ← build LLM context block
        │
        ▼
  LLM (OpenAI / Anthropic)      ← generate final answer
        │
        ▼
  JSON response                 ← recipe, steps, substitutions …

Usage
─────
    from src.rag.rag_pipeline import RAGPipeline

    pipeline = RAGPipeline()
    result = await pipeline.run(
        ingredients=["eggs", "flour", "butter"],
        top_k=5,
        context="birthday cake"
    )
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from src.retrieval.retriever import RecipeRetriever, RetrievedRecipe
from src.rag.prompt_templates import (
    SYSTEM_PROMPT,
    RAG_USER_PROMPT,
    SUBSTITUTION_PROMPT,
    NUTRITION_PROMPT,
    format_recipe_context,
)
from src.preprocessing.ingredient_parser import get_substitutions
from src.utils.config import settings


# ─────────────────────────────────────────────────────────
# LLM Client abstraction
# ─────────────────────────────────────────────────────────

class LLMClient:
    """
    Thin wrapper that supports OpenAI and Anthropic models.
    The provider is chosen by settings.llm.provider.
    """

    def __init__(self) -> None:
        self.provider = settings.llm.provider
        self.model = settings.llm.model_name
        self.temperature = settings.llm.temperature
        self.max_tokens = settings.llm.max_tokens

        if self.provider == "openai":
            from openai import AsyncOpenAI  # lazy import
            self._client = AsyncOpenAI(api_key=settings.llm.api_key)
        elif self.provider == "anthropic":
            import anthropic  # lazy import
            self._client = anthropic.AsyncAnthropic(api_key=settings.llm.api_key)
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{self.provider}'. "
                "Set LLM_PROVIDER=openai or LLM_PROVIDER=anthropic in .env"
            )

    async def chat(self, system: str, user: str) -> str:
        """
        Send a chat completion request and return the response text.

        Parameters
        ----------
        system : str   system / instruction prompt
        user   : str   user-facing prompt

        Returns
        -------
        str  – model's text response
        """
        if self.provider == "openai":
            response = await self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content or ""

        # Anthropic
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text or ""


# ─────────────────────────────────────────────────────────
# JSON parsing helper
# ─────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict:
    """
    Extract JSON from an LLM response that may include prose or fences.

    Attempts:
    1. Direct parse
    2. Extract first {...} block
    3. Strip ```json fences and retry
    """
    text = raw.strip()

    # Attempt 1 – direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2 – extract first JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Attempt 3 – strip fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback – return raw text wrapped in a dict
    logger.warning("Could not parse LLM response as JSON. Returning raw text.")
    return {"raw_response": raw}


# ─────────────────────────────────────────────────────────
# RAG Pipeline
# ─────────────────────────────────────────────────────────

class RAGPipeline:
    """
    End-to-end RAG pipeline: retrieval + LLM generation.

    Parameters
    ----------
    retriever : RecipeRetriever, optional
    llm       : LLMClient, optional
    """

    def __init__(
        self,
        retriever: RecipeRetriever | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._retriever is None:
            self._retriever = RecipeRetriever()
        self._retriever.load()

        if self._llm is None:
            self._llm = LLMClient()

        self._loaded = True

    # ── Main entry point ──────────────────────────────────

    async def run(
        self,
        ingredients: list[str],
        top_k: int | None = None,
        context: str = "",
        include_nutrition: bool = False,
    ) -> dict[str, Any]:
        """
        Full RAG pipeline: retrieve → generate → return structured result.

        Parameters
        ----------
        ingredients      : list[str]  user's available ingredients
        top_k            : int        number of recipes to retrieve
        context          : str        optional free-text hint (cuisine, diet …)
        include_nutrition: bool       whether to add a nutrition estimate

        Returns
        -------
        dict with keys matching the API response schema:
            recipe, score, steps, missing_ingredients, substitutions,
            all_candidates (list of retrieved recipes with scores),
            nutrition (optional)
        """
        self._ensure_loaded()
        top_k = top_k or settings.retrieval.top_k

        # ── Step 1: Retrieve ──────────────────────────────
        logger.info(f"Retrieving top-{top_k} recipes for: {ingredients}")
        candidates: list[RetrievedRecipe] = self._retriever.retrieve(
            ingredients=ingredients,
            top_k=top_k,
            context=context,
        )

        if not candidates:
            return {
                "recipe": "No matching recipe found",
                "score": 0.0,
                "steps": [],
                "missing_ingredients": [],
                "substitutions": {},
                "all_candidates": [],
                "error": "No recipes matched the given ingredients.",
            }

        # ── Step 2: Build LLM context ─────────────────────
        context_recipes = candidates[: settings.llm.context_recipes]
        recipe_context_str = format_recipe_context(context_recipes)

        user_prompt = RAG_USER_PROMPT.format(
            user_ingredients=", ".join(ingredients),
            n_recipes=len(context_recipes),
            recipes_context=recipe_context_str,
        )

        # ── Step 3: LLM generation ────────────────────────
        logger.info("Calling LLM for recipe generation…")
        raw_response = await self._llm.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
        )

        generated = _parse_json_response(raw_response)

        # ── Step 4: Merge static substitution engine ──────
        # Ensure substitutions are filled even if LLM missed some
        best_candidate = candidates[0]
        static_subs = get_substitutions(best_candidate.missing_ingredients)
        merged_subs = {**static_subs, **(generated.get("substitutions") or {})}

        # ── Step 5: (Optional) Nutrition estimate ─────────
        nutrition = None
        if include_nutrition and "recipe" in generated:
            nutrition = await self._get_nutrition(
                recipe_title=generated["recipe"],
                ingredients=ingredients,
            )

        # ── Assemble final response ───────────────────────
        result: dict[str, Any] = {
            "recipe": generated.get("recipe", best_candidate.title),
            "score": best_candidate.combined_score,
            "difficulty": generated.get("difficulty", "Medium"),
            "estimated_time": generated.get("estimated_time", "Unknown"),
            "steps": generated.get("steps", []),
            "missing_ingredients": generated.get(
                "missing_ingredients", best_candidate.missing_ingredients
            ),
            "substitutions": merged_subs,
            "tips": generated.get("tips", ""),
            "score_explanation": generated.get("score_explanation", ""),
            "all_candidates": [c.to_dict() for c in candidates],
        }

        if include_nutrition:
            result["nutrition"] = nutrition

        logger.info(f"Pipeline complete. Best recipe: {result['recipe']}")
        return result

    # ── Nutrition sub-call ────────────────────────────────

    async def _get_nutrition(
        self,
        recipe_title: str,
        ingredients: list[str],
    ) -> dict:
        """Fetch a lightweight nutrition estimate from the LLM."""
        prompt = NUTRITION_PROMPT.format(
            recipe_title=recipe_title,
            ingredients=", ".join(ingredients),
        )
        raw = await self._llm.chat(system=SYSTEM_PROMPT, user=prompt)
        return _parse_json_response(raw)

    # ── Substitution-only mode ────────────────────────────

    async def get_substitutions_only(
        self,
        recipe_title: str,
        missing_ingredients: list[str],
    ) -> dict:
        """
        Lightweight call: ask the LLM for substitutions without full retrieval.

        Parameters
        ----------
        recipe_title        : str
        missing_ingredients : list[str]

        Returns
        -------
        dict  mapping ingredient → substitute
        """
        self._ensure_loaded()

        # First try static lookup
        static = get_substitutions(missing_ingredients)
        missing_without_static = [m for m in missing_ingredients if m not in static]

        if not missing_without_static:
            return static

        prompt = SUBSTITUTION_PROMPT.format(
            recipe_title=recipe_title,
            missing_ingredients=", ".join(missing_without_static),
        )
        raw = await self._llm.chat(system=SYSTEM_PROMPT, user=prompt)
        llm_subs = _parse_json_response(raw)

        return {**static, **llm_subs}
