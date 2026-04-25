"""
src/agent/recipe_graph.py
LangGraph implementation for Recipe Recommendation including Vision extraction.
"""
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage

from src.utils.config import settings
from src.retrieval.retriever import RecipeRetriever
from src.rag.prompt_templates import format_recipe_context, RAG_USER_PROMPT, SYSTEM_PROMPT
from src.rag.rag_pipeline import _parse_json_response, LLMClient

class RecipeState(TypedDict):
    image_base64: Optional[str]
    ingredients: List[str]
    context: str
    top_k: int
    include_nutrition: bool
    
    # Updated by nodes
    vision_extracted_ingredients: List[str]
    retrieved_candidates: List[Any]
    final_recipe: Dict[str, Any]
    error: Optional[str]

async def extract_vision_node(state: RecipeState) -> RecipeState:
    if not state.get("image_base64"):
        return {"vision_extracted_ingredients": []}

    provider = settings.llm.provider
    if provider == "groq":
        from langchain_groq import ChatGroq
        # Vision requires a specific model – different from the text model
        vision_llm = ChatGroq(
            model="llama-3.2-11b-vision-preview",
            api_key=settings.llm.api_key,
            max_tokens=512,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        vision_llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.llm.api_key,
            max_tokens=512,
        )
    else:
        return {"error": f"Vision not supported for provider: {provider}"}

    # Support JPEG, PNG, WEBP — default to jpeg if unknown
    image_b64 = state["image_base64"]
    mime = "image/jpeg"
    if image_b64.startswith("iVBOR"):   # PNG magic bytes in base64
        mime = "image/png"
    elif image_b64.startswith("UklGR"): # WEBP
        mime = "image/webp"

    msg = HumanMessage(
        content=[
            {"type": "text", "text": (
                "Look at this image and list ALL visible raw food ingredients. "
                "Return ONLY a comma-separated list of ingredient names (e.g. tomato, onion, garlic). "
                "No sentences, no explanations, just the comma-separated list."
            )},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{image_b64}"},
            },
        ]
    )
    
    try:
        response = await vision_llm.ainvoke([msg])
        text = response.content.strip()
        # Clean up: remove any leading labels the model may add
        if ":" in text and text.index(":") < 30:
            text = text.split(":", 1)[1].strip()
        found = [i.strip().lower() for i in text.split(',') if i.strip()]
        return {"vision_extracted_ingredients": found}
    except Exception as e:
        return {"error": f"Vision extraction failed: {str(e)}"}

def retrieve_node(state: RecipeState) -> RecipeState:
    if state.get("error"):
        return {}

    retriever = RecipeRetriever()
    retriever.load()
    
    all_ings = state.get("ingredients", []) + state.get("vision_extracted_ingredients", [])
    
    if not all_ings:
        return {"error": "No ingredients provided or found in image."}
        
    candidates = retriever.retrieve(
        ingredients=all_ings,
        top_k=state.get("top_k", 5),
        context=state.get("context", "")
    )
    return {"retrieved_candidates": candidates}

async def generate_node(state: RecipeState) -> RecipeState:
    if state.get("error"):
        return {}
        
    candidates = state.get("retrieved_candidates", [])
    if not candidates:
        return {"final_recipe": {"recipe": "No matching recipe found", "error": "No recipes matched."}}
        
    context_recipes = candidates[: settings.llm.context_recipes]
    context_block = format_recipe_context(context_recipes)
    
    all_ings = state.get("ingredients", []) + state.get("vision_extracted_ingredients", [])
    context_hint = state.get("context", "")
    ingredients_str = ", ".join(all_ings)
    if context_hint:
        ingredients_str += f" (preferences: {context_hint})"
    
    user_prompt = RAG_USER_PROMPT.format(
        user_ingredients=ingredients_str,
        n_recipes=len(context_recipes),
        recipes_context=context_block
    )
    
    llm = LLMClient()
    try:
        response_text = await llm.chat(SYSTEM_PROMPT, user_prompt)
        final_json = _parse_json_response(response_text)
        final_json["all_candidates"] = [c.to_dict() for c in candidates]
        final_json["vision_ingredients"] = state.get("vision_extracted_ingredients", [])
        return {"final_recipe": final_json}
    except Exception as e:
        return {"error": f"Recipe generation failed: {str(e)}"}

# Build Graph
workflow = StateGraph(RecipeState)
workflow.add_node("vision_extract", extract_vision_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "vision_extract")
workflow.add_edge("vision_extract", "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

recipe_agent = workflow.compile()
