import { useState } from 'react';
import { api } from '../services/api';

export default function SubstitutionsTab({ onAskAI }) {
  const [recipeName, setRecipeName] = useState('Pancakes');
  const [missing, setMissing] = useState('milk, eggs');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleFind = async () => {
    const ings = missing.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipeName.trim() || !ings.length) { setError('Fill in both fields.'); return; }
    setError(''); setLoading(true); setResult(null);
    try {
      const data = await api.substitutions({ recipe_title: recipeName.trim(), missing_ingredients: ings });
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const subs = result?.substitutions || {};

  return (
    <div>
      <div className="card">
        <h2 className="section-title">🔄 Ingredient Substitutions</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1.25rem' }}>
          Missing an ingredient? Find smart alternatives instantly.
        </p>
        <div className="form-grid form-grid-2" style={{ marginBottom: '1rem' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">🍲 Recipe Name</label>
            <input className="form-input" value={recipeName} onChange={e => setRecipeName(e.target.value)}
              placeholder="e.g. Pancakes, Pasta..." />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">❌ Missing Ingredients (comma-separated)</label>
            <input className="form-input" value={missing} onChange={e => setMissing(e.target.value)}
              placeholder="milk, eggs, butter..." />
          </div>
        </div>
        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}
        <button className="btn btn-primary" onClick={handleFind} disabled={loading}>
          {loading ? '⏳ Finding...' : '🔍 Find Substitutions'}
        </button>
      </div>

      {loading && (
        <div className="spinner-wrap"><div className="spinner" /><span>Finding the best substitutes...</span></div>
      )}

      {result && (
        <div className="card">
          <h3 className="section-title">Substitutions for: <span style={{ color: 'var(--primary)' }}>{result.recipe}</span></h3>
          {Object.keys(subs).length === 0 ? (
            <div className="alert alert-info">No substitutions found for those ingredients.</div>
          ) : Object.entries(subs).map(([ing, sub]) => {
            const items = Array.isArray(sub) ? sub : [sub];
            return (
              <div key={ing} style={{ marginBottom: '1.25rem' }}>
                <div style={{ marginBottom: '0.5rem' }}>
                  <span className="missing-badge">{ing}</span>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginLeft: '0.5rem' }}>can be replaced with:</span>
                </div>
                {items.map((item, i) => (
                  <div className="sub-item" key={i}>
                    <span className="sub-item-text">• {item}</span>
                    {onAskAI && (
                      <button className="btn btn-ghost btn-sm"
                        onClick={() => onAskAI(`Tell me about using "${item}" as a substitute for "${ing}" in ${result.recipe}.`)}>
                        Ask AI
                      </button>
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
