"""RAG pipeline: retrieve relevant recipes then generate a response with an LLM."""

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


class LLMClient:
    """Thin wrapper that supports OpenAI, Anthropic, and Groq models."""

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
        elif self.provider == "groq":
            from groq import AsyncGroq  # lazy import
            self._client = AsyncGroq(api_key=settings.llm.api_key)
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{self.provider}'. "
                "Set LLM_PROVIDER=openai, anthropic, or groq in .env"
            )

    async def chat(self, system: str, user: str, history: list[dict] | None = None) -> str:
        """Send a chat completion request and return the response text."""
        if self.provider in ("openai", "groq"):
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user})

            response = await self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        # Anthropic
        user_msgs = history if history else []
        user_msgs.append({"role": "user", "content": user})
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=user_msgs,
        )
        return response.content[0].text or ""


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from an LLM response that may include prose or markdown fences."""
    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    logger.warning("Could not parse LLM response as JSON. Returning raw text.")
    return {"raw_response": raw}


class RAGPipeline:
    """End-to-end RAG pipeline: retrieval + LLM generation."""

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

    async def run(
        self,
        ingredients: list[str],
        top_k: int | None = None,
        context: str = "",
        include_nutrition: bool = False,
    ) -> dict[str, Any]:
        """Full RAG pipeline: retrieve → generate → return structured result."""
        self._ensure_loaded()
        top_k = top_k or settings.retrieval.top_k

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

        context_recipes = candidates[: settings.llm.context_recipes]
        recipe_context_str = format_recipe_context(context_recipes)

        user_prompt = RAG_USER_PROMPT.format(
            user_ingredients=", ".join(ingredients),
            n_recipes=len(context_recipes),
            recipes_context=recipe_context_str,
        )

        logger.info("Calling LLM for recipe generation…")
        raw_response = await self._llm.chat(system=SYSTEM_PROMPT, user=user_prompt)
        generated = _parse_json_response(raw_response)

        # Merge static substitutions with LLM-generated ones
        best_candidate = candidates[0]
        static_subs = get_substitutions(best_candidate.missing_ingredients)
        merged_subs = {**static_subs, **(generated.get("substitutions") or {})}

        nutrition = None
        if include_nutrition and "recipe" in generated:
            nutrition = await self._get_nutrition(
                recipe_title=generated["recipe"],
                ingredients=ingredients,
            )

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

    async def _get_nutrition(self, recipe_title: str, ingredients: list[str]) -> dict:
        """Fetch a lightweight nutrition estimate from the LLM."""
        prompt = NUTRITION_PROMPT.format(
            recipe_title=recipe_title,
            ingredients=", ".join(ingredients),
        )
        raw = await self._llm.chat(system=SYSTEM_PROMPT, user=prompt)
        return _parse_json_response(raw)

    async def get_substitutions_only(
        self,
        recipe_title: str,
        missing_ingredients: list[str],
    ) -> dict:
        """Ask the LLM for substitutions without running full retrieval."""
        self._ensure_loaded()

        # Try static lookup first
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
