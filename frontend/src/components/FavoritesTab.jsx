import { useState, useEffect } from 'react';
import RecipeResult from './RecipeResult';

export default function FavoritesTab({ onAskAI }) {
  const [favorites, setFavorites] = useState([]);
  const [history, setHistory] = useState([]);
  const [selectedRecipe, setSelectedRecipe] = useState(null);

  const loadData = () => {
    setFavorites(JSON.parse(localStorage.getItem('recipeFavorites') || '[]'));
    setHistory(JSON.parse(localStorage.getItem('recipeHistory') || '[]'));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleBack = () => {
    setSelectedRecipe(null);
    loadData();
  };

  if (selectedRecipe) {
    return (
      <div>
        <button className="btn btn-ghost" onClick={handleBack} style={{ marginBottom: '1rem' }}>
          ← Back to List
        </button>
        <RecipeResult data={selectedRecipe} servings={selectedRecipe.servings || 2} onAskAI={onAskAI} />
      </div>
    );
  }

  const renderCard = (rec, idx, type) => (
    <div className="recipe-card" key={`${type}-${idx}`} onClick={() => setSelectedRecipe(rec)}>
      <div className="recipe-card-header">
        <div>
          <span className="recipe-card-title">{rec.recipe || 'Recipe'}</span>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            {type === 'fav' ? `Saved: ${new Date(rec.savedAt).toLocaleDateString()}` : `Generated: ${new Date(rec.timestamp).toLocaleDateString()}`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="score-badge" style={{ background: type === 'fav' ? 'var(--warning)' : 'var(--primary-dark)', color: type === 'fav' ? '#000' : '#fff' }}>
            {type === 'fav' ? '⭐' : '🕒'}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="form-grid form-grid-2">
      <div className="card" style={{ height: 'fit-content' }}>
        <h2 className="section-title">⭐ Favorite Recipes</h2>
        {favorites.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No favorite recipes saved yet.</p>
        ) : (
          favorites.map((f, i) => renderCard(f, i, 'fav'))
        )}
      </div>
      <div className="card" style={{ height: 'fit-content' }}>
        <h2 className="section-title">🕒 Recent History</h2>
        {history.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No generated recipes yet.</p>
        ) : (
          history.slice(0, 15).map((h, i) => renderCard(h, i, 'hist'))
        )}
      </div>
    </div>
  );
}
