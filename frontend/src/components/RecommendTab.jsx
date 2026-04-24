import { useState, useEffect } from 'react';
import { api } from '../services/api';
import RecipeResult from './RecipeResult';

const CUISINES = ['Any','Indian','Italian','Mexican','Chinese','Japanese','Mediterranean','American','French','Thai','Middle Eastern','Korean','Greek','Spanish','Vietnamese','Lebanese'];
const COOK_TIMES = ['Any','Under 15 mins','Under 30 mins','Under 45 mins','Under 1 hour'];
const DIFFICULTIES = ['Any','Easy','Medium','Hard'];
const CALORIES = ['Any','Under 300 kcal','Under 500 kcal','Under 800 kcal','Under 1000 kcal'];

export default function RecommendTab({ onAskAI }) {
  const [ingredients, setIngredients] = useState('eggs, milk, flour, sugar');
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
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

  useEffect(() => {
    const p = JSON.parse(localStorage.getItem('recipePantry') || '["salt", "pepper", "olive oil"]');
    setPantry(p);
  }, []);

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
    let ings = ingredients.split(',').map(s => s.trim()).filter(Boolean);
    if (usePantry && pantry.length > 0) {
      ings = [...ings, ...pantry];
    }
    
    if (!ings.length && !image) { setError('Please enter at least one ingredient or upload an image.'); return; }
    setError(''); setLoading(true); setResult(null);

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
      
      // If AI detected ingredients from image, auto-fill them for next time
      if (data.vision_ingredients && data.vision_ingredients.length > 0) {
        setIngredients(prev => {
          const combined = [...new Set([...prev.split(',').map(i=>i.trim()), ...data.vision_ingredients])].filter(Boolean);
          return combined.join(', ');
        });
        // Clear image after successful processing so it doesn't get re-sent
        setImage(null);
        setImagePreview(null);
      }

      setResult(data);
      
      // Save to local storage history
      const history = JSON.parse(localStorage.getItem('recipeHistory') || '[]');
      const newEntry = { ...data, timestamp: new Date().toISOString(), servings };
      const newHistory = [newEntry, ...history].slice(0, 50); // keep last 50
      localStorage.setItem('recipeHistory', JSON.stringify(newHistory));
      
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div className="card">
        <h2 className="section-title">✨ Personalized Recommendation</h2>
        <div className="form-grid form-grid-2">
          <div>
            <div className="form-group">
              <label className="form-label">
                🧺 Ingredients 
                <span style={{ float: 'right', fontSize: '0.8rem', fontWeight: 'normal' }}>
                  <label style={{ cursor: 'pointer', color: 'var(--primary)' }}>
                    📸 Upload Image
                    <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => {
                      const file = e.target.files[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = (event) => {
                        setImagePreview(event.target.result);
                        setImage(event.target.result.split(',')[1]);
                      };
                      reader.readAsDataURL(file);
                    }} />
                  </label>
                </span>
              </label>
              {imagePreview && (
                <div style={{ marginBottom: '0.5rem', position: 'relative', display: 'inline-block' }}>
                  <img src={imagePreview} alt="Upload preview" style={{ height: '80px', borderRadius: '4px', border: '1px solid var(--border)' }} />
                  <button onClick={() => { setImage(null); setImagePreview(null); }} 
                    style={{ position: 'absolute', top: '-5px', right: '-5px', background: 'var(--error)', color: '#fff', border: 'none', borderRadius: '50%', width: '20px', height: '20px', cursor: 'pointer', fontSize: '10px' }}>
                    ✕
                  </button>
                </div>
              )}
              <textarea className="form-textarea" value={ingredients} onChange={e => setIngredients(e.target.value)}
                placeholder="eggs, milk, flour, sugar..." />
            </div>
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
            {loading ? '⏳ Generating...' : '🚀 Generate Recommendation'}
          </button>
          {result && !loading && (
            <button className="btn btn-ghost" onClick={handleSubmit}>
              🔄 Regenerate
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <span>Finding the best {cuisine !== 'Any' ? cuisine + ' ' : ''}recipe for you...</span>
        </div>
      )}

      {result && <RecipeResult data={result} servings={servings} onAskAI={onAskAI} />}
    </div>
  );
}
