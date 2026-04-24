import { useState, useRef } from 'react';
import AISidebar from './components/AISidebar';
import RecommendTab from './components/RecommendTab';
import QuickSearchTab from './components/QuickSearchTab';
import SubstitutionsTab from './components/SubstitutionsTab';
import './index.css';

const TABS = [
  { id: 'recommend', label: '✨ Recommend Recipe' },
  { id: 'search',    label: '🔍 Quick Search' },
  { id: 'subs',      label: '🔄 Substitutions' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('recommend');
  const askAIRef = useRef(null);

  // Called by child components when "Ask AI" button is clicked
  const handleAskAI = (query) => {
    if (askAIRef.current) askAIRef.current(query);
  };

  return (
    <div className="app-layout">
      {/* ── Main scrollable content ── */}
      <div className="main-content">
        <div className="app-header">
          <h1>🍳 Recipe GenAI System</h1>
          <p>Discover personalized recipes, quick searches, and smart substitutions — powered by AI.</p>
        </div>

        {/* Tab Navigation */}
        <nav className="tab-nav">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        {activeTab === 'recommend' && <RecommendTab onAskAI={handleAskAI} />}
        {activeTab === 'search'    && <QuickSearchTab onAskAI={handleAskAI} />}
        {activeTab === 'subs'      && <SubstitutionsTab onAskAI={handleAskAI} />}
      </div>

      {/* ── Fixed AI Sidebar ── */}
      <AISidebar onAskAI={askAIRef} />
    </div>
  );
}
