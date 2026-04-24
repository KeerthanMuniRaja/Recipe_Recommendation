import streamlit as st
import requests
import ast

st.title("Recipe GenAI")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "rec_data" not in st.session_state:
    st.session_state.rec_data = None
if "qs_data" not in st.session_state:
    st.session_state.qs_data = None
if "sub_data" not in st.session_state:
    st.session_state.sub_data = None

api_base = st.text_input("API Base URL", value="http://localhost:8000")

def ask_ai(query: str, context: str = ""):
    st.session_state.messages.append({"role": "user", "content": query})
    try:
        res = requests.post(f"{api_base}/api/v1/chat", json={"message": query, "context": context})
        res.raise_for_status()
        reply = res.json().get("reply", "No reply")
        st.session_state.messages.append({"role": "assistant", "content": reply})
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error contacting AI: {e}"})

# --- Recommend Recipe ---
st.header("Recommend Recipe")
ingredients_str = st.text_area("Ingredients (comma-separated)", "eggs, milk, flour")
context_hint = st.text_input("Context / Dietary Hint", "")
top_k = st.number_input("Top K", min_value=1, value=5)
include_nutrition = st.checkbox("Include Nutrition", value=False)

if st.button("Get Recommendation"):
    ingredients = [i.strip() for i in ingredients_str.split(",") if i.strip()]
    if not ingredients:
        st.warning("Enter some ingredients")
    else:
        try:
            res = requests.post(f"{api_base}/api/v1/recommend", json={
                "ingredients": ingredients,
                "context": context_hint,
                "top_k": top_k,
                "include_nutrition": include_nutrition
            })
            res.raise_for_status()
            st.session_state.rec_data = res.json()
        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.rec_data:
    data = st.session_state.rec_data
    if "error" in data:
        st.error(data["error"])
    else:
        with st.expander(data.get("recipe", "Recipe"), expanded=True):
            st.write("Match Score:", data.get("score"))
            st.write("Difficulty:", data.get("difficulty"))
            st.write("Estimated Time:", data.get("estimated_time"))
            
            st.write("**Steps:**")
            for step in data.get("steps", []):
                st.write(step)
                
            if data.get("tips"):
                st.write("**Tips:**", data.get("tips"))
                
            if data.get("missing_ingredients"):
                st.write("**Missing Ingredients:**", ", ".join(data.get("missing_ingredients")))
                
            if data.get("substitutions"):
                st.write("**Substitutions:**")
                for missing, sub in data.get("substitutions").items():
                    st.write(f"**{missing}** ->")
                    if isinstance(sub, str) and sub.startswith("[") and sub.endswith("]"):
                        try:
                            sub = ast.literal_eval(sub)
                        except Exception:
                            pass
                    if isinstance(sub, list):
                        for i, item in enumerate(sub):
                            col1, col2 = st.columns([3, 1])
                            col1.write(f"- {item}")
                            if col2.button("Ask AI", key=f"rec_ask_{missing}_{i}_{item}"):
                                ask_ai(f"Tell me about using {item} as a substitute for {missing}.")
                    else:
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"- {sub}")
                        if col2.button("Ask AI", key=f"rec_ask_{missing}_{sub}"):
                            ask_ai(f"Tell me about using {sub} as a substitute for {missing}.")
            
            if include_nutrition and data.get("nutrition"):
                st.write("**Nutrition:**")
                for k, v in data.get("nutrition").items():
                    st.write(f"- {k}: {v}")

# --- Quick Search ---
st.header("Quick Search")
q_ings_str = st.text_input("Quick Search Ingredients (comma-separated)", "eggs")
if st.button("Search"):
    q_ings = [i.strip() for i in q_ings_str.split(",") if i.strip()]
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
    st.write(f"Found {data.get('total_found', 0)} recipes")
    for i, rec in enumerate(data.get("recipes", [])):
        with st.expander(rec.get("title", "Recipe")):
            st.write("**Match Score:**", f"{int(rec.get('combined_score', 0)*100)}%")
            st.write("**Matched Ingredients:**", ", ".join(rec.get("matched_ingredients", [])))
            st.write("**Missing Ingredients:**", ", ".join(rec.get("missing_ingredients", [])))
            if st.button("Ask AI about this recipe", key=f"qs_ask_{i}"):
                ask_ai(f"Tell me more about the recipe '{rec.get('title')}'")

# --- Substitutions ---
st.header("Substitutions")
recipe_name = st.text_input("Recipe Name", "Cake")
missing_ings_str = st.text_input("Missing Ingredients (comma-separated)", "milk")
if st.button("Get Substitutions"):
    m_ings = [i.strip() for i in missing_ings_str.split(",") if i.strip()]
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
    with st.expander(f"Substitutions for: {data.get('recipe', recipe_name)}", expanded=True):
        subs = data.get("substitutions", {})
        if subs:
            for missing, sub in subs.items():
                st.write(f"**{missing}** ->")
                if isinstance(sub, str) and sub.startswith("[") and sub.endswith("]"):
                    try:
                        sub = ast.literal_eval(sub)
                    except Exception:
                        pass
                if isinstance(sub, list):
                    for i, item in enumerate(sub):
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"- {item}")
                        if col2.button("Ask AI", key=f"sub_ask_{missing}_{i}_{item}"):
                            ask_ai(f"Tell me about using {item} as a substitute for {missing}.")
                else:
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"- {sub}")
                    if col2.button("Ask AI", key=f"sub_ask_{missing}_{sub}"):
                        ask_ai(f"Tell me about using {sub} as a substitute for {missing}.")
        else:
            st.write("No substitutions found.")

# --- Chat Interface ---
st.divider()
st.header("AI Assistant Chat")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask a culinary question..."):
    ask_ai(prompt)
    st.rerun()
