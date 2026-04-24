import streamlit as st
import requests
import ast

st.set_page_config(
    page_title="Recipe GenAI",
    page_icon="",
    layout="wide"
)

st.markdown("""
<style>
/* Make the right AI column sticky so it stays on screen while scrolling the main page */
div[data-testid="stHorizontalBlock"]:first-of-type > div:nth-child(2) {
    position: sticky !important;
    top: 4rem !important;
    align-self: flex-start !important;
    z-index: 100 !important;
}
</style>
""", unsafe_allow_html=True)

# --- Session State Init ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rec_data" not in st.session_state:
    st.session_state.rec_data = None
if "qs_data" not in st.session_state:
    st.session_state.qs_data = None
if "sub_data" not in st.session_state:
    st.session_state.sub_data = None

api_base = "http://localhost:8000"

def ask_ai(query: str, context: str = ""):
    st.session_state.messages.append({"role": "user", "content": query})
    try:
        res = requests.post(f"{api_base}/api/v1/chat", json={"message": query, "context": context})
        res.raise_for_status()
        reply = res.json().get("reply", "No reply")
        st.session_state.messages.append({"role": "assistant", "content": reply})
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error contacting AI: {e}"})

main_col, chat_col = st.columns([3, 1], gap="large")

with chat_col:
    st.header("🤖 AI Assistant")
    st.markdown("Ask any culinary questions or tap **Ask AI** on recipes!")
    st.divider()
    
    # Chat History
    msg_count = len(st.session_state.messages)
    container_height = max(500, max(50, msg_count * 100))
    chat_container = st.container(height=container_height, border=False)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat Input
    if prompt := st.chat_input("Ask a question..."):
        ask_ai(prompt)
        st.rerun()

with main_col:
    st.title("🍳 Recipe GenAI System")
    st.markdown("Discover personalized recipes, quick searches, and smart substitutions.")
    
    # --- Main Tabs ---
    tab1, tab2, tab3 = st.tabs(["✨ Recommend Recipe", "🔍 Quick Search", "🔄 Substitutions"])
    
    with tab1:
        st.header("Personalized Recommendation")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            ingredients_str = st.text_area("What ingredients do you have? (comma-separated)", "eggs, milk, flour, sugar")
            cuisine_type = st.selectbox(
                "🌍 Cuisine Type",
                options=[
                    "Any", "Indian", "Italian", "Mexican", "Chinese", "Japanese",
                    "Mediterranean", "American", "French", "Thai", "Middle Eastern",
                    "Korean", "Greek", "Spanish", "Vietnamese", "Lebanese"
                ],
                index=0,
                help="Select the cuisine style you prefer. This guides the AI to suggest matching dishes."
            )
            context_hint = st.text_input("Dietary Hint (Optional)", placeholder="E.g., breakfast, vegan, gluten-free")
        
        with col2:
            top_k = st.number_input("Candidates to consider", min_value=1, max_value=20, value=5)
            include_nutrition = st.checkbox("Include Nutrition Estimate", value=False)
            st.markdown("<br>", unsafe_allow_html=True)
            btn_rec = st.button("Generate Recommendation", use_container_width=True, type="primary")
    
        if btn_rec:
            ingredients = [i.strip() for i in ingredients_str.split(",") if i.strip()]
            if not ingredients:
                st.warning("Please enter some ingredients.")
            else:
                # Build combined context: cuisine + dietary hint
                context_parts = []
                if cuisine_type != "Any":
                    context_parts.append(f"{cuisine_type} cuisine")
                if context_hint.strip():
                    context_parts.append(context_hint.strip())
                combined_context = ", ".join(context_parts)

                with st.spinner(f"Finding {''.join([cuisine_type + ' ']) if cuisine_type != 'Any' else ''}recipes with your ingredients..."):
                    try:
                        res = requests.post(f"{api_base}/api/v1/recommend", json={
                            "ingredients": ingredients,
                            "context": combined_context,
                            "top_k": top_k,
                            "include_nutrition": include_nutrition
                        })
                        res.raise_for_status()
                        st.session_state.rec_data = res.json()
                    except Exception as e:
                        st.error(f"Error: {e}")
    
        if st.session_state.rec_data:
            data = st.session_state.rec_data
            st.divider()
            if "error" in data:
                st.error(data["error"])
            else:
                st.subheader(data.get("recipe", "Your Custom Recipe"))
                c1, c2, c3 = st.columns(3)
                c1.metric("Match Score", f"{int(data.get('score', 0) * 100)}%")
                c2.metric("Difficulty", data.get("difficulty", "N/A"))
                c3.metric("Estimated Time", data.get("estimated_time", "N/A"))
                
                st.markdown("### Instructions")
                for step in data.get("steps", []):
                    st.write(step)
                    
                col_tips, col_ings = st.columns(2)
                with col_tips:
                    if data.get("tips"):
                        st.info(f"**Chef's Tip:**\n\n{data.get('tips')}")
                    if include_nutrition and data.get("nutrition"):
                        st.success("**Nutrition Estimate:**\n" + "\n".join([f"- **{k}:** {v}" for k, v in data.get("nutrition").items()]))
                
                with col_ings:
                    if data.get("missing_ingredients"):
                        st.warning("**Missing Ingredients:** " + ", ".join(data.get("missing_ingredients")))
                    if data.get("substitutions"):
                        st.markdown("#### Suggested Substitutions")
                        for missing, sub in data.get("substitutions").items():
                            st.markdown(f"**{missing}** can be replaced with:")
                            if isinstance(sub, str) and sub.startswith("[") and sub.endswith("]"):
                                try:
                                    sub = ast.literal_eval(sub)
                                except Exception:
                                    pass
                            
                            if isinstance(sub, list):
                                for i, item in enumerate(sub):
                                    row_c1, row_c2 = st.columns([3, 1])
                                    row_c1.write(f"- {item}")
                                    if row_c2.button("Ask AI", key=f"rec_ask_{missing}_{i}_{item}"):
                                        ask_ai(f"Tell me about using {item} as a substitute for {missing}.")
                            else:
                                row_c1, row_c2 = st.columns([3, 1])
                                row_c1.write(f"- {sub}")
                                if row_c2.button("Ask AI", key=f"rec_ask_{missing}_{sub}"):
                                    ask_ai(f"Tell me about using {sub} as a substitute for {missing}.")
    
    with tab2:
        st.header("Quick Search")
        st.markdown("Fast vector-based search to find recipes in the database without LLM generation.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            q_ings_str = st.text_input("Quick Search Ingredients (comma-separated)", "chicken, rice")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_qs = st.button("Search", use_container_width=True, type="primary")
    
        if btn_qs:
            q_ings = [i.strip() for i in q_ings_str.split(",") if i.strip()]
            with st.spinner("Searching database..."):
                try:
                    res = requests.post(f"{api_base}/api/v1/search/quick", json={
                        "ingredients": q_ings,
                        "top_k": 5,
                        "context": ""
                    })
                    res.raise_for_status()
                    st.session_state.qs_data = res.json()
                except Exception as e:
                    st.error(f"Error: {e}")
    
        if st.session_state.qs_data:
            data = st.session_state.qs_data
            st.divider()
            st.write(f"**Found {data.get('total_found', 0)} recipes**")
            for i, rec in enumerate(data.get("recipes", [])):
                with st.expander(f"{rec.get('title', 'Recipe')} ({int(rec.get('combined_score', 0)*100)}% Match)"):
                    st.write("**Matched Ingredients:**", ", ".join(rec.get("matched_ingredients", [])))
                    st.write("**Missing Ingredients:**", ", ".join(rec.get("missing_ingredients", [])))
                    if st.button("Ask AI about this recipe", key=f"qs_ask_{i}"):
                        ask_ai(f"Tell me more about the recipe '{rec.get('title')}'")
    
    with tab3:
        st.header("Ingredient Substitutions")
        st.markdown("Quickly find alternatives for missing ingredients in a specific recipe.")
        
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("Recipe Name", "Pancakes")
        with col2:
            missing_ings_str = st.text_input("Missing Ingredients (comma-separated)", "milk, eggs")
            
        btn_sub = st.button("Find Substitutions", type="primary")
    
        if btn_sub:
            m_ings = [i.strip() for i in missing_ings_str.split(",") if i.strip()]
            with st.spinner("Finding best substitutes..."):
                try:
                    res = requests.post(f"{api_base}/api/v1/substitutions", json={
                        "recipe_title": recipe_name,
                        "missing_ingredients": m_ings
                    })
                    res.raise_for_status()
                    st.session_state.sub_data = res.json()
                except Exception as e:
                    st.error(f"Error: {e}")
    
        if st.session_state.sub_data:
            data = st.session_state.sub_data
            st.divider()
            st.subheader(f"Substitutions for: {data.get('recipe', recipe_name)}")
            subs = data.get("substitutions", {})
            if subs:
                for missing, sub in subs.items():
                    st.markdown(f"**{missing}** can be replaced with:")
                    if isinstance(sub, str) and sub.startswith("[") and sub.endswith("]"):
                        try:
                            sub = ast.literal_eval(sub)
                        except Exception:
                            pass
                    
                    if isinstance(sub, list):
                        for i, item in enumerate(sub):
                            row_c1, row_c2 = st.columns([3, 1])
                            row_c1.write(f"- {item}")
                            if row_c2.button("Ask AI", key=f"sub_ask_{missing}_{i}_{item}"):
                                ask_ai(f"Tell me about using {item} as a substitute for {missing}.")
                    else:
                        row_c1, row_c2 = st.columns([3, 1])
                        row_c1.write(f"- {sub}")
                        if row_c2.button("Ask AI", key=f"sub_ask_{missing}_{sub}"):
                            ask_ai(f"Tell me about using {sub} as a substitute for {missing}.")
            else:
                st.info("No substitutions found.")