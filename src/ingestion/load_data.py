"""
src/ingestion/load_data.py
────────────────────────────────────────────────────────
Responsible for loading raw recipe datasets from disk.
Supports:
  • Food.com Recipes (Kaggle CSV) — RAW_recipes.csv
  • Recipe1M (JSON lines)          — layer1.json
  • Custom JSON                    — any list-of-dicts

All loaders return a normalised pandas DataFrame with
columns: [id, title, ingredients, instructions, tags]
"""

from __future__ import annotations

import json
import ast
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from src.utils.config import settings


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────

def _safe_literal(val) -> list:
    """Parse a stringified Python list safely."""
    if isinstance(val, list):
        return val
    try:
        result = ast.literal_eval(str(val))
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _truncate(df: pd.DataFrame, max_rows: Optional[int]) -> pd.DataFrame:
    if max_rows is not None:
        df = df.head(max_rows)
        logger.info(f"Truncated to {max_rows} rows per config.")
    return df


# ─────────────────────────────────────────────────────────
# Food.com loader
# ─────────────────────────────────────────────────────────

def load_foodcom(path: Optional[Path] = None) -> pd.DataFrame:
    """
    Load the Food.com RAW_recipes.csv dataset.

    Expected columns in the CSV:
        id, name, ingredients, steps, tags

    Returns
    -------
    pd.DataFrame
        Normalised recipe dataframe.
    """
    path = path or settings.paths.raw_data / "RAW_recipes.csv"
    logger.info(f"Loading Food.com dataset from {path}")

    if not path.exists():
        raise FileNotFoundError(
            f"Food.com dataset not found at {path}. "
            "Please download RAW_recipes.csv from Kaggle and place it in data/raw/."
        )

    df = pd.read_csv(path, low_memory=False)
    logger.info(f"Loaded {len(df):,} raw rows.")

    # ── Column mapping ──────────────────────────────────
    df = df.rename(columns={"name": "title", "steps": "instructions"})

    # ── Parse stringified lists ─────────────────────────
    df["ingredients"] = df["ingredients"].apply(_safe_literal)
    df["instructions"] = df["instructions"].apply(_safe_literal)
    df["tags"] = df.get("tags", pd.Series(["[]"] * len(df))).apply(_safe_literal)

    df = df[["id", "title", "ingredients", "instructions", "tags"]].copy()
    df["id"] = df["id"].astype(str)

    df = _truncate(df, settings.preprocessing.max_recipes)
    logger.info(f"Food.com: returning {len(df):,} recipes.")
    return df


# ─────────────────────────────────────────────────────────
# Recipe1M loader
# ─────────────────────────────────────────────────────────

def load_recipe1m(path: Optional[Path] = None) -> pd.DataFrame:
    """
    Load the Recipe1M layer1.json dataset (JSON lines or list).

    JSON structure expected per entry:
        {
          "id": "...",
          "title": "...",
          "ingredients": [{"text": "..."}, ...],
          "instructions": [{"text": "..."}, ...],
          "partition": "train" | "val" | "test"
        }

    Returns
    -------
    pd.DataFrame
    """
    path = path or settings.paths.raw_data / "layer1.json"
    logger.info(f"Loading Recipe1M dataset from {path}")

    if not path.exists():
        raise FileNotFoundError(
            f"Recipe1M dataset not found at {path}. "
            "Please obtain layer1.json and place it in data/raw/."
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    logger.info(f"Loaded {len(raw):,} raw entries.")

    records = []
    for item in raw:
        records.append(
            {
                "id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "ingredients": [
                    ing.get("text", "") for ing in item.get("ingredients", [])
                ],
                "instructions": [
                    step.get("text", "") for step in item.get("instructions", [])
                ],
                "tags": item.get("partition", ""),
            }
        )

    df = pd.DataFrame(records)
    df = _truncate(df, settings.preprocessing.max_recipes)
    logger.info(f"Recipe1M: returning {len(df):,} recipes.")
    return df


# ─────────────────────────────────────────────────────────
# Generic JSON loader
# ─────────────────────────────────────────────────────────

def load_custom_json(path: Path) -> pd.DataFrame:
    """
    Load any JSON file that is a list of recipe dicts.

    Minimum required keys per record: title, ingredients, instructions
    Optional keys: id, tags

    Returns
    -------
    pd.DataFrame
    """
    logger.info(f"Loading custom JSON dataset from {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)

    if "id" not in df.columns:
        df["id"] = df.index.astype(str)
    if "tags" not in df.columns:
        df["tags"] = [[] for _ in range(len(df))]

    df = df[["id", "title", "ingredients", "instructions", "tags"]].copy()
    df = _truncate(df, settings.preprocessing.max_recipes)
    logger.info(f"Custom JSON: returning {len(df):,} recipes.")
    return df


# ─────────────────────────────────────────────────────────
# Auto-detect loader
# ─────────────────────────────────────────────────────────

def load_dataset(source: str = "auto") -> pd.DataFrame:
    """
    Convenience entry-point.  Tries to detect and load available datasets.

    Parameters
    ----------
    source : str
        "foodcom"  – force Food.com loader
        "recipe1m" – force Recipe1M loader
        "auto"     – tries Food.com first, then Recipe1M

    Returns
    -------
    pd.DataFrame
    """
    if source == "foodcom":
        return load_foodcom()
    if source == "recipe1m":
        return load_recipe1m()

    # Auto-detect
    foodcom_path = settings.paths.raw_data / "RAW_recipes.csv"
    recipe1m_path = settings.paths.raw_data / "layer1.json"

    if foodcom_path.exists():
        logger.info("Auto-detected Food.com dataset.")
        return load_foodcom(foodcom_path)
    if recipe1m_path.exists():
        logger.info("Auto-detected Recipe1M dataset.")
        return load_recipe1m(recipe1m_path)

    raise FileNotFoundError(
        "No dataset found in data/raw/. "
        "Please add RAW_recipes.csv (Food.com) or layer1.json (Recipe1M)."
    )
