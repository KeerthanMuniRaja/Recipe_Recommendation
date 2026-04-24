import { useState, useEffect } from 'react';
import RecipeResult from './RecipeResult';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function MealPlannerTab({ onAskAI }) {
  const [favorites, setFavorites] = useState([]);
  const [mealPlan, setMealPlan] = useState({
    Monday: [], Tuesday: [], Wednesday: [], Thursday: [], Friday: [], Saturday: [], Sunday: []
  });
  const [selectedRecipe, setSelectedRecipe] = useState(null);

  useEffect(() => {
    setFavorites(JSON.parse(localStorage.getItem('recipeFavorites') || '[]'));
    const savedPlan = JSON.parse(localStorage.getItem('recipeMealPlan') || '{}');
    
    const initializedPlan = {
      Monday: [], Tuesday: [], Wednesday: [], Thursday: [], Friday: [], Saturday: [], Sunday: []
    };
    Object.keys(savedPlan).forEach(day => {
      if (initializedPlan[day] !== undefined) {
        initializedPlan[day] = savedPlan[day];
      }
    });
    setMealPlan(initializedPlan);
  }, []);

  const handleAdd = (day, recipe) => {
    if (!recipe) return;
    const newPlan = { ...mealPlan, [day]: [...mealPlan[day], recipe] };
    setMealPlan(newPlan);
    localStorage.setItem('recipeMealPlan', JSON.stringify(newPlan));
  };

  const handleRemove = (day, index) => {
    const newPlan = { ...mealPlan };
    newPlan[day].splice(index, 1);
    setMealPlan(newPlan);
    localStorage.setItem('recipeMealPlan', JSON.stringify(newPlan));
  };

  if (selectedRecipe) {
    return (
      <div>
        <button className="btn btn-ghost" onClick={() => setSelectedRecipe(null)} style={{ marginBottom: '1rem' }}>
          ← Back to Planner
        </button>
        <RecipeResult data={selectedRecipe} servings={selectedRecipe.servings || 2} onAskAI={onAskAI} />
      </div>
    );
  }

  return (
    <div>
      <div className="card">
        <h2 className="section-title">📅 Weekly Meal Planner</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1.5rem' }}>
          Assign your favorite recipes to days of the week.
        </p>

        {favorites.length === 0 && (
          <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
            You haven't saved any Favorite recipes yet! Generate a recipe and click the ⭐ Save button to use the meal planner.
          </div>
        )}

        <div style={{ display: 'grid', gap: '1rem' }}>
          {DAYS.map(day => (
            <div key={day} style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--primary-light)' }}>{day}</h3>
                
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <select 
                    className="form-select" 
                    style={{ width: '200px', padding: '0.4rem 2rem 0.4rem 0.8rem', fontSize: '0.8rem' }}
                    onChange={(e) => {
                      if (e.target.value) {
                        const rec = favorites.find(f => f.recipe === e.target.value);
                        if (rec) handleAdd(day, rec);
                        e.target.value = ''; // reset
                      }
                    }}
                    disabled={favorites.length === 0}
                  >
                    <option value="">+ Add meal...</option>
                    {favorites.map((f, i) => (
                      <option key={i} value={f.recipe}>{f.recipe}</option>
                    ))}
                  </select>
                </div>
              </div>

              {mealPlan[day].length === 0 ? (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No meals planned.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem' }}>
                  {mealPlan[day].map((rec, i) => (
                    <div className="recipe-card" key={i} style={{ margin: 0 }}>
                      <div className="recipe-card-header" style={{ padding: '0.75rem 1rem' }}>
                        <span className="recipe-card-title" style={{ fontSize: '0.9rem', cursor: 'pointer' }} onClick={() => setSelectedRecipe(rec)}>
                          {rec.recipe || 'Recipe'}
                        </span>
                        <button className="btn btn-ghost btn-sm" style={{ padding: '0.2rem 0.5rem' }} onClick={() => handleRemove(day, i)}>
                          ×
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
