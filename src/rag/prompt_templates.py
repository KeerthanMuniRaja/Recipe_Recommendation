"""
src/rag/prompt_templates.py
────────────────────────────────────────────────────────
All LLM prompt templates for the Recipe RAG pipeline.

Templates are plain Python strings with {placeholder} slots.
Using plain strings (not LangChain PromptTemplate) keeps the
module dependency-free and easy to test.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────
# System prompt (sets the AI persona)
# ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a world-class chef and culinary assistant. \
Your role is to help users cook delicious meals based on the ingredients they have at home.

Guidelines:
- Be warm, encouraging, and practical.
- Always provide clear, numbered step-by-step cooking instructions.
- If an ingredient is missing, suggest the best substitution.
- Mention approximate cooking time and difficulty level.
- Be concise but complete — a home cook should be able to follow your instructions without confusion.
- If asked about nutrition or dietary needs, address them helpfully.
- Never make up ingredients or steps not supported by the retrieved context."""


# ─────────────────────────────────────────────────────────
# Main RAG user prompt
# ─────────────────────────────────────────────────────────

RAG_USER_PROMPT = """
I have the following ingredients at home:
{user_ingredients}

Below are {n_recipes} relevant recipes retrieved from our recipe database.
Use them as context to provide refined, personalised cooking instructions.

─── RETRIEVED RECIPES ──────────────────────────────────
{recipes_context}
────────────────────────────────────────────────────────

Please recommend the BEST recipe from the above context for my ingredients.
Respond in the following JSON structure (and nothing else — no markdown fences):

{{
  "recipe": "<recipe name>",
  "difficulty": "<Easy | Medium | Hard>",
  "estimated_time": "<e.g. 30 minutes>",
  "steps": [
    "<step 1>",
    "<step 2>",
    ...
  ],
  "missing_ingredients": ["<ingredient>", ...],
  "substitutions": {{
    "<missing ingredient>": "<suggested substitute>"
  }},
  "tips": "<optional chef's tip>",
  "score_explanation": "<brief reason why this recipe is the best match>"
}}
"""


# ─────────────────────────────────────────────────────────
# Helper: format retrieved recipes for the context block
# ─────────────────────────────────────────────────────────

def format_recipe_context(retrieved_recipes: list) -> str:
    """
    Convert a list of RetrievedRecipe objects into a numbered
    context block to inject into the RAG prompt.

    Parameters
    ----------
    retrieved_recipes : list[RetrievedRecipe]

    Returns
    -------
    str
    """
    blocks = []
    for i, recipe in enumerate(retrieved_recipes, start=1):
        title = recipe.title if hasattr(recipe, "title") else recipe.get("title", "")
        ingredients = (
            recipe.ingredients
            if hasattr(recipe, "ingredients")
            else recipe.get("ingredients", [])
        )
        instructions = (
            recipe.instructions
            if hasattr(recipe, "instructions")
            else recipe.get("instructions", "")
        )
        score = (
            recipe.combined_score
            if hasattr(recipe, "combined_score")
            else recipe.get("combined_score", 0)
        )
        missing = (
            recipe.missing_ingredients
            if hasattr(recipe, "missing_ingredients")
            else recipe.get("missing_ingredients", [])
        )

        if isinstance(ingredients, list):
            ingredient_str = ", ".join(str(i) for i in ingredients[:20])
        else:
            ingredient_str = str(ingredients)

        blocks.append(
            f"[Recipe {i}] {title}  (match score: {score:.2f})\n"
            f"Ingredients: {ingredient_str}\n"
            f"Missing from your pantry: {', '.join(missing) if missing else 'none'}\n"
            f"Instructions:\n{instructions}\n"
        )
    return "\n".join(blocks)


# ─────────────────────────────────────────────────────────
# Substitution-only prompt (lightweight call)
# ─────────────────────────────────────────────────────────

SUBSTITUTION_PROMPT = """
I am cooking "{recipe_title}" and I am missing the following ingredients:
{missing_ingredients}

Please suggest the best available substitutes for each missing ingredient.
Respond only with a JSON object mapping each ingredient to its best substitute:
{{
  "<ingredient>": "<substitute>",
  ...
}}
"""


# ─────────────────────────────────────────────────────────
# Nutrition analysis prompt
# ─────────────────────────────────────────────────────────

NUTRITION_PROMPT = """
Provide a brief nutritional estimate for the following recipe:

Recipe: {recipe_title}
Ingredients: {ingredients}

Respond with a JSON object:
{{
  "calories_per_serving": <number>,
  "protein_g": <number>,
  "carbs_g": <number>,
  "fat_g": <number>,
  "fiber_g": <number>,
  "notes": "<dietary notes, e.g. gluten-free, vegan-friendly>"
}}
"""
