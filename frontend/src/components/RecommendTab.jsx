import { useState } from 'react';
import { api } from '../services/api';
import RecipeResult from './RecipeResult';

const CUISINES = ['Any','Indian','Italian','Mexican','Chinese','Japanese','Mediterranean','American','French','Thai','Middle Eastern','Korean','Greek','Spanish','Vietnamese','Lebanese'];
const COOK_TIMES = ['Any','Under 15 mins','Under 30 mins','Under 45 mins','Under 1 hour'];
const DIFFICULTIES = ['Any','Easy','Medium','Hard'];

export default function RecommendTab({ onAskAI }) {
  const [ingredients, setIngredients] = useState('eggs, milk, flour, sugar');
  const [cuisine, setCuisine] = useState('Any');
  const [cookTime, setCookTime] = useState('Any');
  const [difficulty, setDifficulty] = useState('Any');
  const [servings, setServings] = useState(2);
  const [topK, setTopK] = useState(5);
  const [dietHint, setDietHint] = useState('');
  const [nutrition, setNutrition] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    const ings = ingredients.split(',').map(s => s.trim()).filter(Boolean);
    if (!ings.length) { setError('Please enter at least one ingredient.'); return; }
    setError(''); setLoading(true); setResult(null);

    const parts = [];
    if (cuisine !== 'Any') parts.push(`${cuisine} cuisine`);
    if (difficulty !== 'Any') parts.push(`${difficulty} difficulty`);
    if (cookTime !== 'Any') parts.push(cookTime.toLowerCase());
    parts.push(`serves ${servings} people`);
    if (dietHint.trim()) parts.push(dietHint.trim());

    try {
      const data = await api.recommend({
        ingredients: ings,
        context: parts.join(', '),
        top_k: topK,
        include_nutrition: nutrition,
      });
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
              <label className="form-label">🧺 Ingredients (comma-separated)</label>
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
