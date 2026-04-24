import { useState } from 'react';
import { api } from '../services/api';

function RecipeCard({ rec, index, onAskAI }) {
  const [open, setOpen] = useState(false);
  const score = Math.round((rec.combined_score || 0) * 100);
  return (
    <div className="recipe-card">
      <div className="recipe-card-header" onClick={() => setOpen(o => !o)}>
        <span className="recipe-card-title">{rec.title || 'Recipe'}</span>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="score-badge">{score}% Match</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>
      {open && (
        <div className="recipe-card-body">
          <div style={{ marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>Matched:</span>
            {(rec.matched_ingredients || []).map(ing => (
              <span className="ingredient-tag" key={ing}>{ing}</span>
            ))}
          </div>
          {rec.missing_ingredients?.length > 0 && (
            <div style={{ marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>Missing:</span>
              {rec.missing_ingredients.map(ing => (
                <span className="ingredient-tag missing" key={ing}>{ing}</span>
              ))}
            </div>
          )}
          {onAskAI && (
            <button className="btn btn-ghost btn-sm"
              onClick={() => onAskAI(`Tell me more about how to make "${rec.title}".`)}>
              🤖 Ask AI about this recipe
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function QuickSearchTab({ onAskAI }) {
  const [ingredients, setIngredients] = useState('chicken, rice');
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const handleSearch = async () => {
    const ings = ingredients.split(',').map(s => s.trim()).filter(Boolean);
    if (!ings.length) { setError('Enter at least one ingredient.'); return; }
    setError(''); setLoading(true); setResults(null);
    try {
      const data = await api.quickSearch({ ingredients: ings, top_k: topK, context: '' });
      setResults(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div className="card">
        <h2 className="section-title">🔍 Quick Search</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1.25rem' }}>
          Fast vector search — finds matching recipes without LLM generation. Instant results!
        </p>
        <div className="form-grid form-grid-2" style={{ marginBottom: '1rem' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">🧺 Ingredients</label>
            <input className="form-input" value={ingredients} onChange={e => setIngredients(e.target.value)}
              placeholder="chicken, rice, garlic..." onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">🔢 Number of Results: <span style={{ color: 'var(--primary)' }}>{topK}</span></label>
            <input type="range" min={1} max={15} value={topK} onChange={e => setTopK(+e.target.value)}
              style={{ marginTop: '0.6rem' }} />
          </div>
        </div>
        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
          {loading ? '⏳ Searching...' : '🔍 Search Recipes'}
        </button>
      </div>

      {loading && (
        <div className="spinner-wrap"><div className="spinner" /><span>Searching recipe database...</span></div>
      )}

      {results && (
        <div className="card">
          <div className="section-title">
            Found <span style={{ color: 'var(--primary)' }}>{results.total_found}</span> recipes
          </div>
          {(results.recipes || []).map((rec, i) => (
            <RecipeCard key={i} rec={rec} index={i} onAskAI={onAskAI} />
          ))}
        </div>
      )}
    </div>
  );
}
