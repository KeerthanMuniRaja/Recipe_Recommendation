"""
src/preprocessing/ingredient_parser.py
────────────────────────────────────────────────────────
Parses and normalises raw ingredient strings.

What it does
────────────
1. Remove quantities (numbers + fractions)
2. Remove units (cups, tbsp, grams …)
3. Remove preparation notes (chopped, diced, freshly …)
4. Strip punctuation and collapse whitespace
5. Lowercase and transliterate

Additionally provides:
  • match_ingredients(user_ingredients, recipe_ingredients)
      → (matched, missing, score)
  • SUBSTITUTIONS lookup table
"""

from __future__ import annotations

import re
from typing import Union

from unidecode import unidecode


# ─────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────

# Fractions: ½, ¾, 1/2, 3/4 …
_RE_FRACTION = re.compile(r"[\u00bc-\u00be\u2150-\u215e]|\d+\s*/\s*\d+")

# Integers and decimals with optional trailing dot/comma
_RE_NUMBER = re.compile(r"\b\d+(\.\d+)?\b")

# Common cooking units (singular & plural variants)
_UNITS = (
    "teaspoon|tsp|tablespoon|tbsp|cup|cups|pint|quart|gallon|"
    "ounce|oz|pound|lb|gram|g|kilogram|kg|ml|milliliter|liter|litre|"
    "pinch|dash|handful|bunch|slice|slices|piece|pieces|sprig|sprigs|"
    "clove|cloves|head|heads|stalk|stalks|can|cans|package|packages|"
    "jar|jars|bottle|bottles|sheet|sheets|leaf|leaves"
)
_RE_UNITS = re.compile(
    rf"\b({_UNITS})\b\.?", re.IGNORECASE
)

# Preparation / descriptor words
_PREP_WORDS = (
    "chopped|diced|minced|sliced|grated|shredded|crushed|peeled|"
    "trimmed|halved|quartered|cubed|roughly|finely|thinly|freshly|"
    "frozen|thawed|cooked|raw|dried|ground|packed|sifted|softened|"
    "melted|warm|cold|hot|large|medium|small|extra|optional|divided|"
    "to taste|as needed|or more|or less|about|approximately"
)
_RE_PREP = re.compile(
    rf"\b({_PREP_WORDS})\b", re.IGNORECASE
)

# Parenthetical notes: (about 2 oz), (optional)
_RE_PARENS = re.compile(r"\(.*?\)")

# Trailing punctuation / junk
_RE_JUNK = re.compile(r"[,;:\-–—/\\|+*&%$#@!?]")

# Collapse whitespace
_RE_SPACES = re.compile(r"\s{2,}")


# ─────────────────────────────────────────────────────────
# Core normaliser
# ─────────────────────────────────────────────────────────

def normalise_ingredient(raw: str) -> str:
    """
    Convert a raw ingredient string to a normalised name.

    Example
    -------
    "2 cups finely chopped onions"  →  "onions"
    "1/2 tsp freshly ground black pepper"  →  "black pepper"

    Parameters
    ----------
    raw : str

    Returns
    -------
    str  – normalised ingredient name (lowercase, no quantities/units/prep)
    """
    text = str(raw)
    text = unidecode(text)              # transliterate accents
    text = _RE_PARENS.sub(" ", text)   # drop parentheticals
    text = _RE_FRACTION.sub(" ", text) # drop fractions
    text = _RE_NUMBER.sub(" ", text)   # drop numbers
    text = _RE_UNITS.sub(" ", text)    # drop units
    text = _RE_PREP.sub(" ", text)     # drop prep words
    text = _RE_JUNK.sub(" ", text)     # drop junk chars
    text = text.lower().strip()
    text = _RE_SPACES.sub(" ", text)
    return text


def normalise_ingredient_list(ingredients: list[str]) -> list[str]:
    """
    Normalise a list of ingredients, dropping empty strings.

    Parameters
    ----------
    ingredients : list[str]

    Returns
    -------
    list[str]
    """
    normed = [normalise_ingredient(i) for i in ingredients]
    return [i for i in normed if i]


# ─────────────────────────────────────────────────────────
# Ingredient matching
# ─────────────────────────────────────────────────────────

def match_ingredients(
    user_ingredients: list[str],
    recipe_ingredients: list[str],
) -> dict:
    """
    Compare normalised user ingredients against a recipe's ingredient list.

    Uses substring matching: an ingredient is "matched" if the user's
    normalised term appears anywhere in the recipe's normalised ingredient
    (or vice versa).

    Parameters
    ----------
    user_ingredients  : list[str]  (already normalised or raw)
    recipe_ingredients: list[str]  (already normalised or raw)

    Returns
    -------
    dict with keys:
        matched   – list of recipe ingredients the user has
        missing   – list of recipe ingredients the user lacks
        score     – float in [0, 1], fraction of recipe covered by user
    """
    user_normed = set(normalise_ingredient_list(user_ingredients))
    recipe_normed = normalise_ingredient_list(recipe_ingredients)

    matched = []
    missing = []

    for ri in recipe_normed:
        # Check if any user ingredient is a substring of the recipe ingredient
        # or if the recipe ingredient is a substring of any user ingredient
        hit = any(
            (u in ri) or (ri in u)
            for u in user_normed
            if len(u) > 2  # skip trivial tokens
        )
        if hit:
            matched.append(ri)
        else:
            missing.append(ri)

    total = len(recipe_normed) if recipe_normed else 1
    score = len(matched) / total

    return {"matched": matched, "missing": missing, "score": round(score, 4)}


# ─────────────────────────────────────────────────────────
# Substitution lookup table
# ─────────────────────────────────────────────────────────

SUBSTITUTIONS: dict[str, list[str]] = {
    # Dairy
    "butter": ["margarine", "coconut oil", "olive oil (3/4 the amount)"],
    "milk": ["oat milk", "almond milk", "soy milk", "coconut milk"],
    "heavy cream": ["coconut cream", "evaporated milk", "half-and-half"],
    "buttermilk": ["plain yogurt", "milk + 1 tbsp lemon juice", "sour cream"],
    "cream cheese": ["ricotta", "mascarpone", "greek yogurt"],
    # Eggs
    "egg": [
        "flax egg (1 tbsp ground flax + 3 tbsp water)",
        "chia egg (1 tbsp chia + 3 tbsp water)",
        "unsweetened applesauce (1/4 cup)",
        "mashed banana (1/4 cup)",
    ],
    # Flour
    "all-purpose flour": [
        "whole wheat flour (3/4 cup per 1 cup)",
        "almond flour (1:1, adjust liquid)",
        "oat flour (1:1)",
        "gluten-free blend (1:1)",
    ],
    "bread flour": ["all-purpose flour + 1 tsp vital wheat gluten per cup"],
    # Sweeteners
    "white sugar": [
        "honey (3/4 cup per 1 cup, reduce liquid by 3 tbsp)",
        "maple syrup (3/4 cup, reduce liquid)",
        "coconut sugar (1:1)",
    ],
    "brown sugar": ["white sugar + 1 tsp molasses per cup", "coconut sugar"],
    "honey": ["maple syrup (1:1)", "agave nectar (1:1)"],
    # Oils & Fats
    "vegetable oil": ["canola oil", "sunflower oil", "melted coconut oil"],
    "olive oil": ["avocado oil", "grapeseed oil"],
    # Proteins
    "chicken": ["turkey", "firm tofu", "chickpeas (for stews)"],
    "beef": ["lamb", "pork", "lentils (for bolognese-style dishes)"],
    "bacon": ["turkey bacon", "smoked tempeh", "pancetta"],
    # Acids
    "lemon juice": ["lime juice", "white wine vinegar", "apple cider vinegar"],
    "vinegar": ["lemon juice", "lime juice"],
    # Aromatics
    "garlic": ["garlic powder (1/8 tsp per clove)", "shallots"],
    "onion": ["shallots", "leeks", "onion powder (1 tsp per medium onion)"],
    # Thickeners
    "cornstarch": ["arrowroot (1:1)", "tapioca starch (1:1)", "potato starch (1:1)"],
    "gelatin": ["agar-agar (use 1/2 the amount)"],
    # Leavening
    "baking powder": ["baking soda + cream of tartar (1/4 tsp soda + 1/2 tsp cream per tsp)"],
    "baking soda": ["baking powder (3x the amount, reduce salt)"],
    # Chocolate
    "dark chocolate": ["semi-sweet chocolate chips", "cacao powder + coconut oil"],
    "cocoa powder": ["carob powder", "dark chocolate (melt & adjust sugar)"],
    # Vegetables
    "spinach": ["kale", "swiss chard", "arugula"],
    "zucchini": ["yellow squash", "cucumber (raw applications)"],
    "broccoli": ["cauliflower", "broccolini", "green beans"],
    # Grains
    "rice": ["quinoa", "couscous", "cauliflower rice"],
    "pasta": ["zucchini noodles", "spaghetti squash", "rice noodles"],
    "breadcrumbs": ["crushed crackers", "rolled oats", "panko"],
}


def get_substitutions(missing_ingredients: list[str]) -> dict[str, list[str]]:
    """
    Return substitution suggestions for a list of missing ingredients.

    Uses fuzzy substring matching against the SUBSTITUTIONS keys.

    Parameters
    ----------
    missing_ingredients : list[str]  (normalised)

    Returns
    -------
    dict  mapping ingredient → [substitution, ...]
    """
    result = {}
    for ingredient in missing_ingredients:
        ingredient = ingredient.lower().strip()
        # Direct key match
        if ingredient in SUBSTITUTIONS:
            result[ingredient] = SUBSTITUTIONS[ingredient]
            continue
        # Substring match
        for key, subs in SUBSTITUTIONS.items():
            if key in ingredient or ingredient in key:
                result[ingredient] = subs
                break
    return result
