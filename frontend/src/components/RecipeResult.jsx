import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { jsPDF } from 'jspdf';

function buildRecipeText(data, servings) {
  let txt = `# ${data.recipe || 'Recipe'}\n\n`;
  txt += `Difficulty: ${data.difficulty || 'N/A'} | Time: ${data.estimated_time || 'N/A'} | Serves: ${servings}\n\n`;
  txt += `## Instructions\n`;
  (data.steps || []).forEach(s => { txt += `${s}\n`; });
  if (data.tips) txt += `\n## Chef's Tip\n${data.tips}\n`;
  return txt;
}

function SubList({ subs, onAskAI }) {
  return Object.entries(subs).map(([missing, sub]) => {
    const items = Array.isArray(sub) ? sub : [sub];
    return (
      <div key={missing} style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
          <span className="missing-badge">{missing}</span> can be replaced with:
        </div>
        {items.map((item, i) => (
          <div className="sub-item" key={i}>
            <span className="sub-item-text">• {item}</span>
            {onAskAI && (
              <button className="btn btn-ghost btn-sm"
                onClick={() => onAskAI(`Tell me about using "${item}" as a substitute for "${missing}".`)}>
                Ask AI
              </button>
            )}
          </div>
        ))}
      </div>
    );
  });
}

export default function RecipeResult({ data, servings, onAskAI }) {
  const [showRaw, setShowRaw] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);

  useEffect(() => {
    if (!data) return;
    const favs = JSON.parse(localStorage.getItem('recipeFavorites') || '[]');
    setIsFavorite(favs.some(f => f.recipe === data.recipe));
  }, [data]);

  const toggleFavorite = () => {
    const favs = JSON.parse(localStorage.getItem('recipeFavorites') || '[]');
    if (isFavorite) {
      const newFavs = favs.filter(f => f.recipe !== data.recipe);
      localStorage.setItem('recipeFavorites', JSON.stringify(newFavs));
      setIsFavorite(false);
    } else {
      const newFavs = [{ ...data, servings, savedAt: new Date().toISOString() }, ...favs];
      localStorage.setItem('recipeFavorites', JSON.stringify(newFavs));
      setIsFavorite(true);
    }
  };

  if (!data) return null;
  if (data.error) return <div className="alert alert-error">{data.error}</div>;

  const recipeText = buildRecipeText(data, servings);

  const handleDownloadTXT = () => {
    const blob = new Blob([recipeText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${data.recipe || 'recipe'}.txt`; a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPDF = () => {
    const doc = new jsPDF();
    doc.setFont("helvetica");
    doc.setFontSize(16);
    doc.text(data.recipe || 'Recipe', 20, 20);
    doc.setFontSize(12);
    doc.text(`Difficulty: ${data.difficulty || 'N/A'} | Time: ${data.estimated_time || 'N/A'} | Serves: ${servings}`, 20, 30);
    
    doc.setFontSize(14);
    doc.text("Instructions:", 20, 45);
    doc.setFontSize(12);
    let y = 55;
    (data.steps || []).forEach((s, i) => {
      const lines = doc.splitTextToSize(`${i+1}. ${s}`, 170);
      doc.text(lines, 20, y);
      y += lines.length * 7;
      if (y > 280) { doc.addPage(); y = 20; }
    });

    if (data.tips) {
      y += 10;
      if (y > 280) { doc.addPage(); y = 20; }
      doc.setFontSize(14);
      doc.text("Chef's Tip:", 20, y);
      y += 10;
      doc.setFontSize(12);
      const lines = doc.splitTextToSize(data.tips, 170);
      doc.text(lines, 20, y);
    }
    
    doc.save(`${data.recipe || 'recipe'}.pdf`);
  };

  return (
    <div className="card">
      <div className="recipe-header">
        <h2 className="recipe-title">{data.recipe || 'Your Recipe'}</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0, alignItems: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={toggleFavorite} style={{ color: isFavorite ? 'var(--warning)' : 'inherit' }}>
            {isFavorite ? '⭐ Saved' : '☆ Save'}
          </button>
          <button className="download-btn" onClick={handleDownloadPDF}>📄 PDF</button>
          <button className="download-btn" onClick={handleDownloadTXT}>📋 TXT</button>
        </div>
      </div>

      <div className="metrics-row">
        <div className="metric-card">
          <div className="metric-label">Match Score</div>
          <div className="metric-value">{Math.round((data.score || 0) * 100)}%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Difficulty</div>
          <div className="metric-value" style={{ fontSize: '1rem' }}>{data.difficulty || 'N/A'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Est. Time</div>
          <div className="metric-value" style={{ fontSize: '1rem' }}>{data.estimated_time || 'N/A'}</div>
        </div>
      </div>

      <h3 className="section-title">📋 Instructions</h3>
      {(data.steps || []).map((step, i) => (
        <div className="recipe-step" key={i}>
          <span className="step-num">{i + 1}.</span>
          <span>{step}</span>
        </div>
      ))}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1.5rem' }}>
        <div>
          {data.tips && (
            <div className="tip-box" style={{ marginBottom: '1rem' }}>
              <h4>👨‍🍳 Chef's Tip</h4>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{data.tips}</p>
            </div>
          )}
          {data.nutrition && (
            <div className="nutrition-box">
              <h4>🥗 Nutrition Estimate</h4>
              <div className="nutrition-grid">
                {Object.entries(data.nutrition).map(([k, v]) => (
                  <div className="nutrition-item" key={k}>{k}: <span>{v}</span></div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div>
          {data.missing_ingredients?.length > 0 && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
              <strong>Missing Ingredients:</strong> {data.missing_ingredients.join(', ')}
            </div>
          )}
          {data.substitutions && Object.keys(data.substitutions).length > 0 && (
            <div>
              <h4 className="section-title" style={{ fontSize: '0.9rem' }}>🔄 Substitutions</h4>
              <SubList subs={data.substitutions} onAskAI={onAskAI} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
