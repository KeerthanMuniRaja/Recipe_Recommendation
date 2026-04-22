# 🍳 Recipe GenAI System

> **RAG-powered recipe recommendations from your available ingredients.**  
> Built with Sentence Transformers, FAISS, FastAPI, and an OpenAI/Anthropic LLM.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Folder Structure](#folder-structure)
4. [Quick Start](#quick-start)
5. [Dataset Setup](#dataset-setup)
6. [Build Pipeline](#build-pipeline)
7. [Running the API](#running-the-api)
8. [API Reference](#api-reference)
9. [Configuration](#configuration)
10. [Docker](#docker)
11. [Testing](#testing)
12. [Evaluation](#evaluation)
13. [Extending the System](#extending-the-system)

---

## Overview

The Recipe GenAI System accepts a list of ingredients you have at home and returns:

| Output Field | Description |
|---|---|
| `recipe` | Best matching recipe name |
| `score` | Combined similarity + ingredient coverage score (0–1) |
| `steps` | LLM-refined step-by-step cooking instructions |
| `missing_ingredients` | Ingredients the recipe needs that you don't have |
| `substitutions` | Suggested alternatives for missing ingredients |
| `all_candidates` | All retrieved candidate recipes with scores |
| `nutrition` *(optional)* | Estimated calories, protein, carbs, fat |

---

## Architecture

```
User Ingredients
      │
      ▼
┌─────────────────────┐
│  Preprocessing      │  Remove quantities, units, prep words
│  ingredient_parser  │  Normalise: "2 cups finely chopped onion" → "onion"
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  RecipeEmbedder     │  sentence-transformers/all-MiniLM-L6-v2
│  (Query Encoding)   │  → normalised 384-dim float32 vector
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  RecipeVectorStore  │  FAISS IndexFlatIP (cosine via dot product)
│  (FAISS Search)     │  → top-k candidate recipes + similarity scores
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Post-processing    │  ingredient matching, missing detection,
│  (Retriever)        │  substitution lookup, combined re-ranking
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  RAG Pipeline       │  Format context → call LLM
│  (LLM Generation)   │  → JSON: steps, tips, substitutions
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  FastAPI            │  /api/v1/recommend  /api/v1/substitutions
│  (REST API)         │  /api/v1/search/quick  /api/v1/health
└─────────────────────┘
```

---

## Folder Structure

```
recipe-genai-system/
│
├── data/
│   ├── raw/                    # Drop RAW_recipes.csv or layer1.json here
│   └── processed/              # Auto-generated cleaned parquet files
│
├── notebooks/
│   ├── data_cleaning.ipynb     # Exploratory data cleaning
│   └── embedding_generation.ipynb
│
├── src/
│   ├── ingestion/
│   │   └── load_data.py        # Food.com, Recipe1M, custom JSON loaders
│   │
│   ├── preprocessing/
│   │   ├── clean_text.py       # Title / instruction cleaning
│   │   └── ingredient_parser.py # Quantity removal, matching, substitutions
│   │
│   ├── embedding/
│   │   ├── embedder.py         # SentenceTransformer wrapper
│   │   └── vector_store.py     # FAISS index build / search / persist
│   │
│   ├── retrieval/
│   │   └── retriever.py        # High-level retrieval + re-ranking
│   │
│   ├── rag/
│   │   ├── rag_pipeline.py     # Full RAG pipeline (retrieve → generate)
│   │   └── prompt_templates.py # System + user prompts
│   │
│   ├── api/
│   │   └── app.py              # FastAPI application
│   │
│   ├── utils/
│   │   └── config.py           # Central Settings dataclass
│   │
│   └── build_pipeline.py       # One-shot index builder CLI
│
├── models/
│   └── embeddings/             # FAISS index + metadata (auto-generated)
│
├── tests/
│   └── test_pipeline.py        # Unit + integration tests
│
├── requirements.txt
├── .env.example
├── dockerfile
└── README.md
```

---

## Quick Start

### 1. Clone and create environment

```bash
git clone <repo-url> && cd recipe-genai-system
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY at minimum
```

### 3. Add a dataset

See [Dataset Setup](#dataset-setup) below.

### 4. Build the index

```bash
python -m src.build_pipeline
```

### 5. Start the API

```bash
uvicorn src.api.app:app --reload --port 8000
```

### 6. Make a request

```bash
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{"ingredients": ["eggs", "flour", "butter", "sugar", "milk"], "top_k": 5}'
```

---

## Dataset Setup

Place **one** of the following files in `data/raw/`:

| Dataset | Filename | Source |
|---|---|---|
| **Food.com** (recommended) | `RAW_recipes.csv` | [Kaggle](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions) |
| **Recipe1M** | `layer1.json` | [Recipe1M](http://im2recipe.csail.mit.edu/dataset/download/) |
| **Custom** | any `.json` | See `load_custom_json()` in `load_data.py` |

The `load_dataset(source="auto")` function auto-detects which file is present.

---

## Build Pipeline

```bash
# Auto-detect dataset (recommended)
python -m src.build_pipeline

# Force a specific dataset
python -m src.build_pipeline --source foodcom
python -m src.build_pipeline --source recipe1m

# Limit to 10,000 recipes for testing
MAX_RECIPES=10000 python -m src.build_pipeline
```

The pipeline:
1. Loads and cleans recipes
2. Generates 384-dim sentence embeddings (CPU ~5–15 min for 230k recipes)
3. Builds a FAISS FlatIP index
4. Saves `models/embeddings/recipes.index` and `.meta.pkl`

---

## Running the API

```bash
# Development
uvicorn src.api.app:app --reload --port 8000

# Production
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 4

# Or via the module entry-point
python -m src.api.app
```

Interactive API docs available at: http://localhost:8000/docs

---

## API Reference

### `POST /api/v1/recommend`

Main endpoint. Returns LLM-refined recipe with full details.

**Request body:**
```json
{
  "ingredients": ["eggs", "flour", "butter", "sugar"],
  "top_k": 5,
  "context": "birthday cake, chocolate",
  "include_nutrition": false
}
```

**Response:**
```json
{
  "recipe": "Classic Chocolate Cake",
  "score": 0.87,
  "difficulty": "Medium",
  "estimated_time": "60 minutes",
  "steps": [
    "1. Preheat oven to 350°F (175°C).",
    "2. Cream butter and sugar until fluffy.",
    "..."
  ],
  "missing_ingredients": ["cocoa powder", "baking powder"],
  "substitutions": {
    "cocoa powder": "dark chocolate (melted, adjust sugar)"
  },
  "tips": "Bring all ingredients to room temperature for best results.",
  "score_explanation": "You have 6/8 core ingredients...",
  "all_candidates": [...]
}
```

### `POST /api/v1/search/quick`

FAISS-only search — no LLM call, very fast.

```json
{ "ingredients": ["chicken", "garlic", "lemon"], "top_k": 5 }
```

### `POST /api/v1/substitutions`

Get substitutions for specific missing ingredients.

```json
{
  "recipe_title": "Chocolate Cake",
  "missing_ingredients": ["butter", "eggs"]
}
```

### `GET /api/v1/health`

Returns API status and vector store size.

### `GET /api/v1/store/info`

Returns index statistics (total recipes, embedding model, dimension).

---

## Configuration

All settings live in `src/utils/config.py` and are driven by environment variables.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model |
| `RETRIEVAL_TOP_K` | `5` | Default recipes to retrieve |
| `FAISS_INDEX_TYPE` | `flat` | `flat` or `ivf` |
| `SCORE_THRESHOLD` | `0.2` | Min similarity to include result |
| `MAX_RECIPES` | *(all)* | Limit recipes loaded |

---

## Docker

```bash
# Build
docker build -t recipe-genai .

# Run
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  recipe-genai
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests (no FAISS index required)
pytest tests/ -v -k "not TestAPI"

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

Tests requiring a built index are automatically skipped if `models/embeddings/recipes.index` doesn't exist.

---

## Evaluation

| Metric | How to measure |
|---|---|
| **Retrieval precision@k** | % of top-k results where user ingredients cover ≥50% of recipe |
| **Ingredient coverage score** | Average `ingredient_score` across queries |
| **Latency** | `/api/v1/recommend` p50/p95 via `X-Process-Time-Ms` header |
| **LLM faithfulness** | Steps reference only ingredients in the retrieved recipe context |
| **User satisfaction** | A/B test: thumbs up/down on recommendations |

---

## Extending the System

| Feature | Where to add |
|---|---|
| **Nutritional filtering** | Add Nutritionix API call in `rag_pipeline.py` |
| **Multilingual support** | Use `paraphrase-multilingual-MiniLM-L12-v2` as `EMBEDDING_MODEL` |
| **Dietary filters** | Add `tags` filter in `retriever.py` `retrieve()` |
| **User preferences** | Persist via Redis; inject as `context` string |
| **Larger index** | Switch `FAISS_INDEX_TYPE=ivf` and increase `FAISS_NLIST` |
| **Streaming responses** | Add SSE endpoint using `StreamingResponse` in FastAPI |
