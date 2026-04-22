"""
src/preprocessing/clean_text.py
────────────────────────────────────────────────────────
Utility functions for cleaning raw recipe text.

Pipeline per field
──────────────────
Title        → lowercase, strip punctuation, collapse whitespace
Instructions → join list → strip HTML / markdown, normalise whitespace
Ingredients  → delegated to ingredient_parser.py
"""

from __future__ import annotations

import re
import html
from typing import Union

from unidecode import unidecode


# ─────────────────────────────────────────────────────────
# Regex patterns (compiled once at module load)
# ─────────────────────────────────────────────────────────
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_MARKDOWN_BOLD = re.compile(r"\*{1,2}([^*]+)\*{1,2}")
_RE_MULTI_SPACE = re.compile(r"\s{2,}")
_RE_STEP_NUMBER = re.compile(r"^\s*(\d+[\.\)])\s*")   # "1." or "1)"
_RE_SPECIAL_CHARS = re.compile(r"[^\w\s,.()\-/']")


# ─────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────

def decode_html(text: str) -> str:
    """Unescape HTML entities: &amp; → &, &deg; → °, etc."""
    return html.unescape(text)


def remove_html_tags(text: str) -> str:
    """Strip HTML tags from text."""
    return _RE_HTML_TAG.sub(" ", text)


def remove_markdown(text: str) -> str:
    """Remove common markdown formatting, keeping the inner text."""
    text = _RE_MARKDOWN_BOLD.sub(r"\1", text)
    return text


def normalise_whitespace(text: str) -> str:
    """Collapse multiple spaces / tabs / newlines into a single space."""
    return _RE_MULTI_SPACE.sub(" ", text.replace("\n", " ").replace("\t", " ")).strip()


def transliterate(text: str) -> str:
    """Convert accented / non-ASCII characters to closest ASCII equivalent."""
    return unidecode(text)


# ─────────────────────────────────────────────────────────
# Field-specific cleaners
# ─────────────────────────────────────────────────────────

def clean_title(title: str) -> str:
    """
    Normalise a recipe title.

    Steps: decode HTML → strip tags → transliterate → lowercase → collapse spaces
    """
    if not isinstance(title, str):
        return ""
    title = decode_html(title)
    title = remove_html_tags(title)
    title = transliterate(title)
    title = title.lower()
    title = normalise_whitespace(title)
    return title


def clean_instructions(instructions: Union[list, str]) -> str:
    """
    Convert instructions (list of steps OR raw string) into a single
    clean paragraph.  Step numbers are preserved.

    Returns
    -------
    str
        Human-readable, newline-separated instruction string.
    """
    if isinstance(instructions, list):
        steps = []
        for i, step in enumerate(instructions, start=1):
            step = str(step)
            step = decode_html(step)
            step = remove_html_tags(step)
            step = remove_markdown(step)
            step = transliterate(step)
            step = normalise_whitespace(step)
            if step:
                # Prepend step number if not already present
                if not _RE_STEP_NUMBER.match(step):
                    step = f"{i}. {step}"
                steps.append(step)
        return "\n".join(steps)

    # Raw string path
    text = str(instructions)
    text = decode_html(text)
    text = remove_html_tags(text)
    text = remove_markdown(text)
    text = transliterate(text)
    text = normalise_whitespace(text)
    return text


def clean_tags(tags: Union[list, str]) -> list[str]:
    """
    Normalise a list of recipe tags to lowercase stripped strings.

    Returns
    -------
    list[str]
    """
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        return []
    return [str(t).strip().lower() for t in tags if str(t).strip()]


# ─────────────────────────────────────────────────────────
# DataFrame-level cleaner
# ─────────────────────────────────────────────────────────

def clean_recipe_dataframe(df) -> "pd.DataFrame":
    """
    Apply all text cleaning functions to a recipe DataFrame in-place.

    Expected input columns: id, title, ingredients, instructions, tags
    Added columns: clean_title, clean_instructions, clean_tags

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame  (same object, mutated)
    """
    import pandas as pd  # local import to avoid hard dep at module level

    df = df.copy()

    df["clean_title"] = df["title"].apply(clean_title)
    df["clean_instructions"] = df["instructions"].apply(clean_instructions)
    df["clean_tags"] = df["tags"].apply(clean_tags)

    # Drop rows with empty titles or instructions
    before = len(df)
    df = df[
        (df["clean_title"].str.len() > 0)
        & (df["clean_instructions"].str.len() > 0)
    ].reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        import logging
        logging.getLogger(__name__).info(
            f"Dropped {dropped} rows with empty title or instructions."
        )

    return df
