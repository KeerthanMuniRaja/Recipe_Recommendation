"""
tests/test_pipeline.py
────────────────────────────────────────────────────────
Unit and integration tests for the Recipe GenAI System.

Run:
    pytest tests/ -v
"""

from __future__ import annotations

import json
import pytest
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────
# Preprocessing tests
# ─────────────────────────────────────────────────────────

class TestCleanText:
    def test_clean_title_basic(self):
        from src.preprocessing.clean_text import clean_title
        assert clean_title("  Chicken &amp; Rice  ") == "chicken & rice"

    def test_clean_title_html(self):
        from src.preprocessing.clean_text import clean_title
        assert "<b>" not in clean_title("<b>Pasta</b> Bake")

    def test_clean_instructions_list(self):
        from src.preprocessing.clean_text import clean_instructions
        steps = ["Boil water.", "Add pasta.", "Drain and serve."]
        result = clean_instructions(steps)
        assert "1." in result
        assert "Boil water" in result

    def test_clean_instructions_string(self):
        from src.preprocessing.clean_text import clean_instructions
        raw = "  Mix   everything  together.  "
        assert clean_instructions(raw) == "Mix everything together."

    def test_clean_dataframe(self):
        from src.preprocessing.clean_text import clean_recipe_dataframe
        df = pd.DataFrame([
            {
                "id": "1",
                "title": "  Pasta Bake  ",
                "ingredients": ["flour", "eggs"],
                "instructions": ["Preheat oven.", "Bake 30 min."],
                "tags": ["easy"],
            }
        ])
        result = clean_recipe_dataframe(df)
        assert "clean_title" in result.columns
        assert result.iloc[0]["clean_title"] == "pasta bake"


class TestIngredientParser:
    def test_normalise_removes_quantity(self):
        from src.preprocessing.ingredient_parser import normalise_ingredient
        assert "cup" not in normalise_ingredient("2 cups all-purpose flour")
        assert "flour" in normalise_ingredient("2 cups all-purpose flour")

    def test_normalise_removes_prep_words(self):
        from src.preprocessing.ingredient_parser import normalise_ingredient
        result = normalise_ingredient("3 cloves garlic, minced")
        assert "minced" not in result
        assert "garlic" in result

    def test_normalise_fraction(self):
        from src.preprocessing.ingredient_parser import normalise_ingredient
        result = normalise_ingredient("½ tsp salt")
        assert result.strip() == "salt"

    def test_match_ingredients_full_match(self):
        from src.preprocessing.ingredient_parser import match_ingredients
        user = ["eggs", "flour", "butter"]
        recipe = ["3 large eggs", "2 cups flour", "100g butter"]
        result = match_ingredients(user, recipe)
        assert result["score"] == 1.0
        assert len(result["missing"]) == 0

    def test_match_ingredients_partial(self):
        from src.preprocessing.ingredient_parser import match_ingredients
        user = ["eggs"]
        recipe = ["3 large eggs", "2 cups flour", "100g butter"]
        result = match_ingredients(user, recipe)
        assert result["score"] < 1.0
        assert len(result["missing"]) > 0

    def test_get_substitutions_known(self):
        from src.preprocessing.ingredient_parser import get_substitutions
        subs = get_substitutions(["butter"])
        assert "butter" in subs
        assert len(subs["butter"]) > 0

    def test_get_substitutions_unknown(self):
        from src.preprocessing.ingredient_parser import get_substitutions
        subs = get_substitutions(["unicorn_powder"])
        # No substitution should be returned for unknown ingredient
        assert "unicorn_powder" not in subs


# ─────────────────────────────────────────────────────────
# Embedding tests
# ─────────────────────────────────────────────────────────

class TestEmbedder:
    @pytest.fixture(scope="class")
    def embedder(self):
        from src.embedding.embedder import RecipeEmbedder
        return RecipeEmbedder()

    def test_encode_query_shape(self, embedder):
        vec = embedder.encode_query(["eggs", "flour"])
        assert vec.ndim == 2
        assert vec.shape[0] == 1
        assert vec.shape[1] == embedder.vector_dim

    def test_encode_query_normalised(self, embedder):
        vec = embedder.encode_query(["eggs", "milk", "butter"])
        norm = float(np.linalg.norm(vec[0]))
        assert abs(norm - 1.0) < 1e-4, f"Expected unit vector, got norm={norm}"

    def test_encode_recipes_shape(self, embedder):
        df = pd.DataFrame([
            {
                "clean_title": "pasta",
                "ingredients": ["pasta", "tomato sauce", "cheese"],
            },
            {
                "clean_title": "omelette",
                "ingredients": ["eggs", "butter", "salt"],
            },
        ])
        vecs = embedder.encode_recipes(df, show_progress=False)
        assert vecs.shape == (2, embedder.vector_dim)

    def test_similar_recipes_closer_than_dissimilar(self, embedder):
        """Recipes with overlapping ingredients should be closer."""
        pasta_q = embedder.encode_query(["pasta", "tomato", "cheese"])
        cake_q = embedder.encode_query(["sugar", "butter", "eggs", "flour"])

        pasta_recipe = embedder.encode_query(["spaghetti", "marinara sauce", "parmesan"])
        cake_recipe = embedder.encode_query(["flour", "sugar", "eggs", "vanilla"])

        # Cosine similarity (vectors are normalised → dot product = cosine)
        sim_pasta = float(np.dot(pasta_q[0], pasta_recipe[0]))
        sim_cake_pasta = float(np.dot(pasta_q[0], cake_recipe[0]))

        assert sim_pasta > sim_cake_pasta, (
            "Pasta query should be more similar to pasta recipe than to cake recipe."
        )


# ─────────────────────────────────────────────────────────
# Vector store tests
# ─────────────────────────────────────────────────────────

class TestVectorStore:
    @pytest.fixture(scope="class")
    def populated_store(self, tmp_path_factory):
        from src.embedding.embedder import RecipeEmbedder
        from src.embedding.vector_store import RecipeVectorStore

        tmp = tmp_path_factory.mktemp("models")
        embedder = RecipeEmbedder()

        df = pd.DataFrame([
            {"id": "1", "clean_title": "omelette", "ingredients": ["eggs", "butter", "salt"],
             "clean_instructions": "Beat eggs. Cook in butter.", "clean_tags": []},
            {"id": "2", "clean_title": "pancakes", "ingredients": ["flour", "eggs", "milk", "sugar"],
             "clean_instructions": "Mix batter. Cook on griddle.", "clean_tags": []},
            {"id": "3", "clean_title": "chocolate cake", "ingredients": ["flour", "cocoa", "sugar", "butter"],
             "clean_instructions": "Mix dry ingredients. Bake.", "clean_tags": []},
        ])
        vecs = embedder.encode_recipes(df, show_progress=False)

        store = RecipeVectorStore(
            index_path=tmp / "test.index",
            metadata_path=tmp / "test.meta.pkl",
        )
        store.build(vecs, df)
        return store, embedder

    def test_store_size(self, populated_store):
        store, _ = populated_store
        assert store.size == 3

    def test_search_returns_results(self, populated_store):
        store, embedder = populated_store
        query = embedder.encode_query(["eggs", "butter"])
        results = store.search(query, top_k=2)
        assert len(results) > 0
        assert "clean_title" in results[0] or "title" in results[0]

    def test_search_score_range(self, populated_store):
        store, embedder = populated_store
        query = embedder.encode_query(["flour", "sugar", "butter"])
        results = store.search(query, top_k=3)
        for r in results:
            assert 0.0 <= r["similarity_score"] <= 1.0

    def test_save_load_roundtrip(self, populated_store, tmp_path):
        from src.embedding.vector_store import RecipeVectorStore

        store, embedder = populated_store
        idx_path = tmp_path / "rt.index"
        meta_path = tmp_path / "rt.meta.pkl"

        # Save to temp location
        store.index_path = idx_path
        store.metadata_path = meta_path
        store.save()

        # Load from temp location
        store2 = RecipeVectorStore(index_path=idx_path, metadata_path=meta_path)
        store2.load()

        assert store2.size == store.size

        query = embedder.encode_query(["eggs"])
        r1 = store.search(query, top_k=1)
        r2 = store2.search(query, top_k=1)
        assert r1[0]["id"] == r2[0]["id"]


# ─────────────────────────────────────────────────────────
# API tests
# ─────────────────────────────────────────────────────────

class TestAPI:
    """
    Integration tests for the FastAPI application.
    Uses httpx async test client.
    These tests require a working FAISS index to be built first.
    They are skipped automatically if the index doesn't exist.
    """

    @pytest.fixture(scope="class")
    def client(self):
        import asyncio
        from pathlib import Path
        from src.utils.config import settings

        if not settings.paths.faiss_index.exists():
            pytest.skip(
                "FAISS index not found. Run `python -m src.build_pipeline` first."
            )

        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_health_check(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "vector_store_recipes" in data

    def test_store_info(self, client):
        response = client.get("/api/v1/store/info")
        assert response.status_code == 200
        data = response.json()
        assert "total_recipes_indexed" in data
        assert data["total_recipes_indexed"] > 0

    def test_quick_search(self, client):
        response = client.post(
            "/api/v1/search/quick",
            json={"ingredients": ["eggs", "flour", "butter"], "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert "recipes" in data
        assert len(data["recipes"]) > 0

    def test_recommend_invalid_empty_ingredients(self, client):
        response = client.post(
            "/api/v1/recommend",
            json={"ingredients": []},
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_recommend_response_schema(self, client):
        response = client.post(
            "/api/v1/recommend",
            json={"ingredients": ["eggs", "butter", "flour", "sugar"], "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        # Must have the core required keys
        assert "recipe" in data
        assert "score" in data
        assert "steps" in data
        assert "missing_ingredients" in data
        assert "substitutions" in data

    def test_substitutions_endpoint(self, client):
        response = client.post(
            "/api/v1/substitutions",
            json={
                "recipe_title": "Chocolate Cake",
                "missing_ingredients": ["butter", "eggs"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "substitutions" in data
        assert isinstance(data["substitutions"], dict)


# ─────────────────────────────────────────────────────────
# Prompt template tests
# ─────────────────────────────────────────────────────────

class TestPromptTemplates:
    def test_format_recipe_context(self):
        from src.rag.prompt_templates import format_recipe_context
        from src.retrieval.retriever import RetrievedRecipe

        recipes = [
            RetrievedRecipe(
                id="1",
                title="Test Cake",
                ingredients=["flour", "sugar", "eggs"],
                instructions="1. Mix\n2. Bake",
                combined_score=0.85,
                missing_ingredients=["sugar"],
            )
        ]
        ctx = format_recipe_context(recipes)
        assert "Test Cake" in ctx
        assert "0.85" in ctx
        assert "sugar" in ctx

    def test_rag_user_prompt_format(self):
        from src.rag.prompt_templates import RAG_USER_PROMPT
        rendered = RAG_USER_PROMPT.format(
            user_ingredients="eggs, flour",
            n_recipes=1,
            recipes_context="[Recipe 1] Pancakes | ...",
        )
        assert "eggs, flour" in rendered
        assert "Pancakes" in rendered
