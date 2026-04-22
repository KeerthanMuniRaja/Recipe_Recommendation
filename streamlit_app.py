"""
streamlit_app.py
────────────────────────────────────────────────────────
Streamlit UI for the Recipe GenAI System.

Talks to the FastAPI backend (default: http://localhost:8000).
Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import time
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Recipe GenAI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Hero banner ── */
    .hero-banner {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 16px;
        padding: 2.5rem 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .hero-banner h1 { color: #fff; font-size: 2.4rem; margin: 0; }
    .hero-banner p  { color: #a0aec0; font-size: 1rem; margin: 0.6rem 0 0; }
    .gradient-text {
        background: linear-gradient(90deg, #e96c4c, #e040fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* ── Recipe card ── */
    .recipe-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid rgba(233,108,76,0.4);
        border-radius: 14px;
        padding: 1.6rem;
        margin-bottom: 1rem;
    }
    .recipe-card h2 { color: #e96c4c; margin: 0 0 0.4rem; font-size: 1.5rem; }
    .recipe-card .meta { color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem; }

    /* ── Score badge ── */
    .score-badge {
        display: inline-block;
        background: linear-gradient(90deg, #e96c4c, #e040fb);
        color: #fff;
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* ── Step list ── */
    .step-item {
        background: rgba(255,255,255,0.04);
        border-left: 3px solid #e96c4c;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.5rem;
        color: #e2e8f0;
        font-size: 0.92rem;
    }

    /* ── Tag pill ── */
    .tag-pill {
        display: inline-block;
        background: rgba(224,64,251,0.15);
        border: 1px solid rgba(224,64,251,0.3);
        color: #e040fb;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.75rem;
        margin: 2px;
    }

    /* ── Candidate card ── */
    .candidate-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .candidate-card strong { color: #e2e8f0; }
    .candidate-card span  { color: #64748b; font-size: 0.82rem; }

    /* ── Nutrition grid ── */
    .nutrition-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.8rem;
        margin-top: 0.5rem;
    }
    .nutrition-item {
        background: rgba(255,255,255,0.04);
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .nutrition-item .value { font-size: 1.4rem; font-weight: 700; color: #e96c4c; }
    .nutrition-item .label { font-size: 0.75rem; color: #64748b; margin-top: 2px; }

    /* ── Status dot ── */
    .dot-ok  { color: #22c55e; }
    .dot-err { color: #ef4444; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { background: #0f172a; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────
# Constants / session state init
# ─────────────────────────────────────────────────────────
DEFAULT_API = "http://localhost:8000"

if "api_base" not in st.session_state:
    st.session_state.api_base = DEFAULT_API
if "ingredients" not in st.session_state:
    st.session_state.ingredients = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None


# ─────────────────────────────────────────────────────────
# Helper: API calls
# ─────────────────────────────────────────────────────────

def api_get(path: str, timeout: int = 6) -> dict | None:
    try:
        r = requests.get(f"{st.session_state.api_base}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post(path: str, payload: dict, timeout: int = 60) -> dict | None:
    try:
        r = requests.post(
            f"{st.session_state.api_base}{path}",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


# ─────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.session_state.api_base = st.text_input(
        "API Base URL",
        value=st.session_state.api_base,
        help="URL of the FastAPI backend",
    ).rstrip("/")

    # Health check
    health = api_get("/api/v1/health")
    if health:
        st.markdown(
            f'<span class="dot-ok">●</span> **API Online** — '
            f'{health.get("vector_store_recipes", "?")} recipes indexed',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="dot-err">●</span> **API Offline** — start the backend first',
            unsafe_allow_html=True,
        )

    st.divider()

    # Store info
    with st.expander("🗄️ Vector Store Info"):
        info = api_get("/api/v1/store/info")
        if info:
            st.json(info)
        else:
            st.caption("Unavailable — backend not running.")

    st.divider()
    st.markdown("### 🚀 Quick Start")
    st.code("uvicorn src.api.app:app --reload", language="bash")
    st.code("streamlit run streamlit_app.py", language="bash")

    st.divider()
    st.caption("Recipe GenAI System · FastAPI + FAISS + GPT-4o")


# ─────────────────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="hero-banner">
      <h1>🍳 Recipe <span class="gradient-text">GenAI</span></h1>
      <p>Enter what's in your kitchen — our AI chef builds you a personalised recipe.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────

tab_search, tab_quick, tab_sub = st.tabs(
    ["🧠 AI Recommend", "⚡ Quick Search", "🔄 Substitutions"]
)


# ══════════════════════════════════════════════════════════
# TAB 1 — Full RAG recommendation
# ══════════════════════════════════════════════════════════

with tab_search:
    st.subheader("Ingredient Input")

    col_input, col_add = st.columns([4, 1])
    with col_input:
        new_ing = st.text_input(
            "Type an ingredient",
            placeholder="e.g. eggs, chicken, olive oil…",
            label_visibility="collapsed",
            key="ing_input",
        )
    with col_add:
        add_clicked = st.button("➕ Add", use_container_width=True, key="btn_add")

    if add_clicked and new_ing.strip():
        item = new_ing.strip().lower()
        if item not in st.session_state.ingredients:
            st.session_state.ingredients.append(item)
        st.rerun()

    # Quick-add chips
    st.markdown("**Quick add:**")
    quick = ["🥚 Eggs", "🌾 Flour", "🧈 Butter", "🍗 Chicken",
             "🧄 Garlic", "🍅 Tomatoes", "🍝 Pasta", "🧅 Onion",
             "🫒 Olive Oil", "🍚 Rice", "🥛 Milk", "🧀 Cheese"]

    chip_cols = st.columns(6)
    for i, chip in enumerate(quick):
        name = chip.split(" ", 1)[1].lower()
        if chip_cols[i % 6].button(chip, key=f"chip_{i}", use_container_width=True):
            if name not in st.session_state.ingredients:
                st.session_state.ingredients.append(name)
            st.rerun()

    # Show added ingredients
    if st.session_state.ingredients:
        st.markdown(f"**Added ({len(st.session_state.ingredients)}):**")
        tag_html = "".join(
            f'<span class="tag-pill">🟠 {ing}</span>'
            for ing in st.session_state.ingredients
        )
        st.markdown(tag_html, unsafe_allow_html=True)

        remove_col, clear_col = st.columns([3, 1])
        with remove_col:
            to_remove = st.selectbox(
                "Remove ingredient",
                ["— select —"] + st.session_state.ingredients,
                label_visibility="collapsed",
                key="remove_sel",
            )
        with clear_col:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.ingredients = []
                st.rerun()

        if to_remove != "— select —":
            st.session_state.ingredients.remove(to_remove)
            st.rerun()
    else:
        st.info("No ingredients added yet.")

    st.divider()

    # Options
    st.subheader("Options")
    opt_col1, opt_col2, opt_col3 = st.columns(3)
    with opt_col1:
        context_hint = st.text_input(
            "Cuisine / dietary hint",
            placeholder="e.g. Italian, vegan, low-carb",
        )
    with opt_col2:
        top_k = st.slider("Recipes to retrieve", 1, 10, 5)
    with opt_col3:
        include_nutrition = st.toggle("Include nutrition estimate", value=False)

    # Submit
    st.divider()
    recommend_btn = st.button(
        "🍽️ Find My Recipe",
        type="primary",
        use_container_width=True,
        disabled=len(st.session_state.ingredients) == 0,
    )

    if recommend_btn:
        with st.spinner("🤖 AI is cooking up your recipe…"):
            t0 = time.time()
            result = api_post(
                "/api/v1/recommend",
                {
                    "ingredients": st.session_state.ingredients,
                    "top_k": top_k,
                    "context": context_hint,
                    "include_nutrition": include_nutrition,
                },
            )
            elapsed = round(time.time() - t0, 1)

        if result:
            st.session_state.last_result = result

    # ── Results ──────────────────────────────────────────
    result = st.session_state.last_result
    if result:
        st.divider()

        if "error" in result:
            st.warning(result["error"])
        else:
            # Main recipe card
            score_pct = int(result.get("score", 0) * 100)
            difficulty = result.get("difficulty", "Medium")
            est_time   = result.get("estimated_time", "—")

            st.markdown(
                f"""
                <div class="recipe-card">
                  <h2>📖 {result.get('recipe','')}</h2>
                  <div class="meta">
                    ⏱ {est_time} &nbsp;|&nbsp; 🎯 {difficulty} &nbsp;|&nbsp;
                    <span class="score-badge">Match: {score_pct}%</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            res_col1, res_col2 = st.columns([2, 1])

            with res_col1:
                # Steps
                steps = result.get("steps", [])
                if steps:
                    st.markdown("#### 👨‍🍳 Step-by-step Instructions")
                    for i, step in enumerate(steps, 1):
                        st.markdown(
                            f'<div class="step-item"><strong>Step {i}:</strong> {step}</div>',
                            unsafe_allow_html=True,
                        )

                # Chef's tip
                if result.get("tips"):
                    st.info(f"💡 **Chef's tip:** {result['tips']}")

                # Score explanation
                if result.get("score_explanation"):
                    st.caption(f"🔍 {result['score_explanation']}")

            with res_col2:
                # Missing ingredients
                missing = result.get("missing_ingredients", [])
                if missing:
                    st.markdown("#### ❌ Missing Ingredients")
                    for m in missing:
                        st.markdown(f"- `{m}`")

                # Substitutions
                subs = result.get("substitutions", {})
                if subs:
                    st.markdown("#### 🔄 Substitutions")
                    for ing, sub in subs.items():
                        st.markdown(f"**{ing}** → {sub}")

                # Nutrition
                if include_nutrition and result.get("nutrition"):
                    nut = result["nutrition"]
                    st.markdown("#### 🥗 Nutrition (per serving)")
                    st.markdown(
                        f"""
                        <div class="nutrition-grid">
                          <div class="nutrition-item">
                            <div class="value">{nut.get('calories_per_serving','—')}</div>
                            <div class="label">Calories</div>
                          </div>
                          <div class="nutrition-item">
                            <div class="value">{nut.get('protein_g','—')}g</div>
                            <div class="label">Protein</div>
                          </div>
                          <div class="nutrition-item">
                            <div class="value">{nut.get('carbs_g','—')}g</div>
                            <div class="label">Carbs</div>
                          </div>
                          <div class="nutrition-item">
                            <div class="value">{nut.get('fat_g','—')}g</div>
                            <div class="label">Fat</div>
                          </div>
                          <div class="nutrition-item">
                            <div class="value">{nut.get('fiber_g','—')}g</div>
                            <div class="label">Fiber</div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if nut.get("notes"):
                        st.caption(nut["notes"])

            # All candidates
            candidates = result.get("all_candidates", [])
            if candidates:
                with st.expander(f"📋 All {len(candidates)} Retrieved Candidates"):
                    for c in candidates:
                        pct = int(c.get("combined_score", 0) * 100)
                        matched = ", ".join(c.get("matched_ingredients", [])[:5]) or "—"
                        missing_c = ", ".join(c.get("missing_ingredients", [])[:5]) or "none"
                        st.markdown(
                            f"""
                            <div class="candidate-card">
                              <strong>{c.get('title','')}</strong>
                              <span class="score-badge" style="float:right">{pct}%</span><br/>
                              <span>✅ {matched}</span><br/>
                              <span>❌ Missing: {missing_c}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )


# ══════════════════════════════════════════════════════════
# TAB 2 — Quick Search (retrieval only, no LLM)
# ══════════════════════════════════════════════════════════

with tab_quick:
    st.subheader("⚡ Fast Retrieval (no LLM)")
    st.caption("Uses FAISS vector search only — much faster, no API cost.")

    q_ings_raw = st.text_area(
        "Ingredients (comma-separated)",
        placeholder="eggs, butter, flour, milk",
        height=80,
    )
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        q_top_k = st.slider("Top K", 1, 20, 5, key="q_topk")
    with q_col2:
        q_context = st.text_input("Context hint", placeholder="Italian, vegan…", key="q_ctx")

    if st.button("🔍 Search", type="primary", use_container_width=True):
        q_ings = [i.strip() for i in q_ings_raw.split(",") if i.strip()]
        if not q_ings:
            st.warning("Please enter at least one ingredient.")
        else:
            with st.spinner("Searching vector store…"):
                qresult = api_post(
                    "/api/v1/search/quick",
                    {"ingredients": q_ings, "top_k": q_top_k, "context": q_context},
                )

            if qresult:
                st.success(f"Found **{qresult.get('total_found', 0)}** recipes.")
                for rec in qresult.get("recipes", []):
                    pct = int(rec.get("combined_score", 0) * 100)
                    with st.expander(f"🍴 {rec.get('title','')}  —  {pct}% match"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("**✅ Matched:**")
                            for m in rec.get("matched_ingredients", []):
                                st.markdown(f"- {m}")
                        with c2:
                            st.markdown("**❌ Missing:**")
                            for m in rec.get("missing_ingredients", []):
                                st.markdown(f"- {m}")
                        if rec.get("tags"):
                            tags_html = "".join(
                                f'<span class="tag-pill">{t}</span>'
                                for t in rec["tags"][:8]
                            )
                            st.markdown(tags_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# TAB 3 — Substitutions
# ══════════════════════════════════════════════════════════

with tab_sub:
    st.subheader("🔄 Ingredient Substitutions")
    st.caption("Get AI-powered substitutions for missing ingredients in a recipe.")

    s_title = st.text_input("Recipe name", placeholder="e.g. Chocolate Cake")
    s_missing_raw = st.text_area(
        "Missing ingredients (comma-separated)",
        placeholder="buttermilk, cream of tartar",
        height=80,
    )

    if st.button("🔄 Get Substitutions", type="primary", use_container_width=True):
        s_missing = [i.strip() for i in s_missing_raw.split(",") if i.strip()]
        if not s_title or not s_missing:
            st.warning("Please enter both a recipe name and missing ingredients.")
        else:
            with st.spinner("Looking up substitutions…"):
                sresult = api_post(
                    "/api/v1/substitutions",
                    {"recipe_title": s_title, "missing_ingredients": s_missing},
                )

            if sresult:
                st.markdown(f"### Substitutions for **{sresult.get('recipe','')}**")
                subs_dict = sresult.get("substitutions", {})
                if subs_dict:
                    for ing, sub in subs_dict.items():
                        st.markdown(
                            f"""
                            <div class="candidate-card">
                              <strong>🔴 {ing}</strong> &nbsp;→&nbsp; <span style="color:#22c55e">✅ {sub}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("No substitutions found.")
