import { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import RecipeResult from './RecipeResult';

const CUISINES = ['Any','Indian','Italian','Mexican','Chinese','Japanese','Mediterranean','American','French','Thai','Middle Eastern','Korean','Greek','Spanish','Vietnamese','Lebanese'];
const COOK_TIMES = ['Any','Under 15 mins','Under 30 mins','Under 45 mins','Under 1 hour'];
const DIFFICULTIES = ['Any','Easy','Medium','Hard'];
const CALORIES = ['Any','Under 300 kcal','Under 500 kcal','Under 800 kcal','Under 1000 kcal'];

export default function RecommendTab({ onAskAI }) {
  const [mode, setMode] = useState('text'); // 'text' | 'image'
  const [ingredients, setIngredients] = useState('eggs, milk, flour, sugar');
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [detectedIngredients, setDetectedIngredients] = useState([]);
  const [cuisine, setCuisine] = useState('Any');
  const [cookTime, setCookTime] = useState('Any');
  const [difficulty, setDifficulty] = useState('Any');
  const [servings, setServings] = useState(2);
  const [topK, setTopK] = useState(5);
  const [dietHint, setDietHint] = useState('');
  const [maxCalories, setMaxCalories] = useState('Any');
  const [nutrition, setNutrition] = useState(false);

  // Pantry
  const [pantry, setPantry] = useState([]);
  const [newPantryItem, setNewPantryItem] = useState('');
  const [usePantry, setUsePantry] = useState(true);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    const p = JSON.parse(localStorage.getItem('recipePantry') || '["salt", "pepper", "olive oil"]');
    setPantry(p);
  }, []);

  const processFile = (file) => {
    if (!file || !file.type.startsWith('image/')) {
      setError('Please upload a valid image file.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      setImagePreview(event.target.result);
      setImage(event.target.result.split(',')[1]);
      setDetectedIngredients([]);
      setResult(null);
      setError('');
    };
    reader.readAsDataURL(file);
  };

  const handleFileChange = (e) => processFile(e.target.files[0]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    processFile(e.dataTransfer.files[0]);
  };

  const clearImage = () => {
    setImage(null);
    setImagePreview(null);
    setDetectedIngredients([]);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const addPantry = () => {
    const val = newPantryItem.trim();
    if (val && !pantry.includes(val)) {
      const updated = [...pantry, val];
      setPantry(updated);
      localStorage.setItem('recipePantry', JSON.stringify(updated));
    }
    setNewPantryItem('');
  };

  const removePantry = (item) => {
    const updated = pantry.filter(i => i !== item);
    setPantry(updated);
    localStorage.setItem('recipePantry', JSON.stringify(updated));
  };

  const handleSubmit = async () => {
    let ings = mode === 'text'
      ? ingredients.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    if (usePantry && pantry.length > 0) ings = [...ings, ...pantry];

    if (!ings.length && !image) {
      setError(mode === 'image'
        ? 'Please upload an ingredient image first.'
        : 'Please enter at least one ingredient or upload an image.');
      return;
    }

    setError(''); setLoading(true); setResult(null); setDetectedIngredients([]);

    const parts = [];
    if (cuisine !== 'Any') parts.push(`${cuisine} cuisine`);
    if (difficulty !== 'Any') parts.push(`${difficulty} difficulty`);
    if (cookTime !== 'Any') parts.push(cookTime.toLowerCase());
    if (maxCalories !== 'Any') parts.push(maxCalories.toLowerCase());
    parts.push(`serves ${servings} people`);
    if (dietHint.trim()) parts.push(dietHint.trim());

    try {
      const data = await api.recommend({
        ingredients: ings,
        context: parts.join(', '),
        top_k: topK,
        include_nutrition: nutrition,
        image_base64: image || undefined,
      });

      // Show detected ingredients from image
      if (data.vision_ingredients && data.vision_ingredients.length > 0) {
        setDetectedIngredients(data.vision_ingredients);
        if (mode === 'text') {
          setIngredients(prev => {
            const combined = [...new Set([...prev.split(',').map(i => i.trim()), ...data.vision_ingredients])].filter(Boolean);
            return combined.join(', ');
          });
        }
        // Clear image after successful processing
        setImage(null);
        setImagePreview(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }

      setResult(data);

      // Save to local storage history
      const history = JSON.parse(localStorage.getItem('recipeHistory') || '[]');
      const newEntry = { ...data, timestamp: new Date().toISOString(), servings };
      localStorage.setItem('recipeHistory', JSON.stringify([newEntry, ...history].slice(0, 50)));

    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div>
      {/* ── Mode Toggle ─────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <button
          className={`btn ${mode === 'text' ? 'btn-primary' : 'btn-ghost'}`}
          style={{ flex: 1, fontSize: '0.9rem' }}
          onClick={() => { setMode('text'); clearImage(); }}
        >
          ✏️ Type Ingredients
        </button>
        <button
          className={`btn ${mode === 'image' ? 'btn-primary' : 'btn-ghost'}`}
          style={{ flex: 1, fontSize: '0.9rem' }}
          onClick={() => { setMode('image'); setResult(null); setDetectedIngredients([]); }}
        >
          📸 Scan Ingredient Image
        </button>
      </div>

      <div className="card">
        <h2 className="section-title">✨ Personalized Recommendation</h2>
        <div className="form-grid form-grid-2">
          <div>

            {/* ── IMAGE MODE ──────────────────────────────── */}
            {mode === 'image' && (
              <div className="form-group">
                <label className="form-label">📸 Upload Ingredient Photo</label>
                <div
                  onClick={() => !imagePreview && fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  style={{
                    border: `2px dashed ${isDragging ? 'var(--primary)' : imagePreview ? 'var(--success, #22c55e)' : 'var(--border)'}`,
                    borderRadius: '12px',
                    padding: imagePreview ? '0.75rem' : '2.5rem 1rem',
                    textAlign: 'center',
                    cursor: imagePreview ? 'default' : 'pointer',
                    background: isDragging ? 'rgba(99,102,241,0.07)' : 'var(--surface)',
                    transition: 'all 0.2s ease',
                    minHeight: '160px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                    position: 'relative',
                  }}
                >
                  {imagePreview ? (
                    <>
                      <img
                        src={imagePreview}
                        alt="Ingredient preview"
                        style={{ maxHeight: '160px', maxWidth: '100%', borderRadius: '8px', objectFit: 'contain' }}
                      />
                      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()}>
                          🔄 Change
                        </button>
                        <button
                          className="btn btn-sm"
                          style={{ background: 'var(--error, #ef4444)', color: '#fff', border: 'none' }}
                          onClick={(e) => { e.stopPropagation(); clearImage(); }}
                        >
                          🗑️ Remove
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: '2.5rem' }}>🥦</div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        Drag & drop or click to upload
                      </div>
                      <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                        Upload a photo of ingredients — AI will identify them and suggest recipes
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                        Supports JPG, PNG, WEBP
                      </div>
                    </>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                />

                {/* Optional extra ingredients alongside image */}
                <div style={{ marginTop: '0.75rem' }}>
                  <label className="form-label" style={{ fontSize: '0.82rem' }}>
                    ➕ Add extra ingredients (optional, combined with image scan)
                  </label>
                  <input
                    className="form-input"
                    value={ingredients}
                    onChange={e => setIngredients(e.target.value)}
                    placeholder="e.g. salt, pepper, olive oil..."
                  />
                </div>
              </div>
            )}

            {/* ── TEXT MODE ───────────────────────────────── */}
            {mode === 'text' && (
              <div className="form-group">
                <label className="form-label">🧺 Ingredients</label>
                <textarea
                  className="form-textarea"
                  value={ingredients}
                  onChange={e => setIngredients(e.target.value)}
                  placeholder="eggs, milk, flour, sugar..."
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">🌍 Cuisine Type</label>
              <select className="form-select" value={cuisine} onChange={e => setCuisine(e.target.value)}>
                {CUISINES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">🥗 Dietary Hint (optional)</label>
              <input className="form-input" value={dietHint} onChange={e => setDietHint(e.target.value)}
                placeholder="e.g. vegan, low-carb, breakfast..." />
            </div>

            <div className="form-group" style={{ marginTop: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <label className="form-label" style={{ margin: 0 }}>🧺 My Pantry Inventory</label>
                <label className="checkbox-label" style={{ fontSize: '0.8rem' }}>
                  <input type="checkbox" checked={usePantry} onChange={e => setUsePantry(e.target.checked)} />
                  Use in Search
                </label>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <input className="form-input" value={newPantryItem} onChange={e => setNewPantryItem(e.target.value)}
                  placeholder="Add staple (e.g. garlic)..." onKeyDown={e => e.key === 'Enter' && addPantry()} />
                <button className="btn btn-ghost" onClick={addPantry}>Add</button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {pantry.length === 0 ? (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Pantry is empty.</span>
                ) : (
                  pantry.map(p => (
                    <span key={p} className="ingredient-tag" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      {p}
                      <span style={{ cursor: 'pointer', opacity: 0.7 }} onClick={() => removePantry(p)}>×</span>
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>

          <div>
            <div className="form-group">
              <label className="form-label">🍽️ Serving Size</label>
              <div className="slider-wrapper">
                <div className="slider-label-row">
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>1</span>
                  <span className="slider-value">{servings} {servings === 1 ? 'person' : 'people'}</span>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>10</span>
                </div>
                <input type="range" min={1} max={10} value={servings} onChange={e => setServings(+e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">⏱️ Max Cook Time</label>
              <select className="form-select" value={cookTime} onChange={e => setCookTime(e.target.value)}>
                {COOK_TIMES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">⭐ Difficulty</label>
              <select className="form-select" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                {DIFFICULTIES.map(d => <option key={d}>{d}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">🔥 Calorie Budget</label>
              <select className="form-select" value={maxCalories} onChange={e => setMaxCalories(e.target.value)}>
                {CALORIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">🔢 Candidates to Consider</label>
              <div className="slider-wrapper">
                <div className="slider-label-row">
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>1</span>
                  <span className="slider-value">{topK}</span>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>20</span>
                </div>
                <input type="range" min={1} max={20} value={topK} onChange={e => setTopK(+e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="checkbox-label">
                <input type="checkbox" checked={nutrition} onChange={e => setNutrition(e.target.checked)} />
                Include Nutrition Estimate
              </label>
            </div>
          </div>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading} style={{ flex: 1 }}>
            {loading
              ? (mode === 'image' ? '🔍 Scanning image & finding recipes...' : '⏳ Generating...')
              : (mode === 'image' ? '🔍 Scan Image & Get Recipes' : '🚀 Generate Recommendation')}
          </button>
          {result && !loading && (
            <button className="btn btn-ghost" onClick={handleSubmit}>🔄 Regenerate</button>
          )}
        </div>
      </div>

      {/* ── Loading ─────────────────────────────────────── */}
      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <span>
            {mode === 'image'
              ? '🔍 AI is scanning your image for ingredients...'
              : `Finding the best ${cuisine !== 'Any' ? cuisine + ' ' : ''}recipe for you...`}
          </span>
        </div>
      )}

      {/* ── Detected Ingredients Banner ─────────────────── */}
      {detectedIngredients.length > 0 && !loading && (
        <div className="card" style={{
          background: 'linear-gradient(135deg, rgba(99,102,241,0.12), rgba(16,185,129,0.08))',
          border: '1px solid rgba(99,102,241,0.3)',
          marginTop: '1rem',
        }}>
          <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', color: 'var(--primary)' }}>
            🤖 AI Detected Ingredients from Your Image
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {detectedIngredients.map(ing => (
              <span key={ing} className="ingredient-tag" style={{
                background: 'rgba(99,102,241,0.15)',
                border: '1px solid rgba(99,102,241,0.4)',
                color: 'var(--primary)',
                fontWeight: 600,
              }}>
                ✅ {ing}
              </span>
            ))}
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.5rem', marginBottom: 0 }}>
            These ingredients were automatically detected from your image and used to find the best recipe.
          </p>
        </div>
      )}

      {result && <RecipeResult data={result} servings={servings} onAskAI={onAskAI} />}
    </div>
  );
}
