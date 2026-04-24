import { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';

export default function AISidebar({ onAskAI }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [width, setWidth] = useState(320);
  const [isDragging, setIsDragging] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendMessage = async (text) => {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const data = await api.chat(q);
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally { setLoading(false); }
  };

  // Expose sendMessage so parent can trigger "Ask AI" button clicks
  useEffect(() => { if (onAskAI) onAskAI.current = sendMessage; }, []);

  const handleKey = (e) => { if (e.key === 'Enter') { e.preventDefault(); sendMessage(); } };

  const startResize = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;
    const onMouseMove = (e) => {
      // Calculate new width based on mouse position
      const newWidth = document.body.clientWidth - e.clientX;
      if (newWidth >= 280 && newWidth <= 800) {
        setWidth(newWidth);
      }
    };
    const onMouseUp = () => setIsDragging(false);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    
    // While dragging, prevent text selection to make it smooth
    document.body.style.userSelect = 'none';
    
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  return (
    <aside className="ai-sidebar" style={{ width: `${width}px`, minWidth: `${width}px` }}>
      <div className="resizer" onMouseDown={startResize} />
      <div className="sidebar-header">
        <div className="sidebar-header-row">
          <span className="sidebar-title"><span>🤖</span> AI Assistant</span>
          {messages.length > 0 && (
            <button className="btn btn-danger btn-sm" onClick={() => setMessages([])}>🗑️ Clear</button>
          )}
        </div>
        <p className="sidebar-subtitle">Ask anything or tap <strong>Ask AI</strong> on results</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <span className="chat-empty-icon">🍽️</span>
            <p>Ask about recipes, tips, substitutions, or cuisine styles!</p>
          </div>
        ) : messages.map((msg, i) => (
          <div key={i}>
            <div className="chat-role">{msg.role === 'user' ? 'You' : 'AI Chef'}</div>
            <div className={`chat-bubble ${msg.role}`}>{msg.content}</div>
          </div>
        ))}
        {loading && (
          <div>
            <div className="chat-role">AI Chef</div>
            <div className="chat-bubble assistant">
              <span className="typing-dot"/><span className="typing-dot"/><span className="typing-dot"/>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <input className="form-input" type="text" placeholder="Ask a question..."
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey} disabled={loading} />
          <button className="send-btn" onClick={() => sendMessage()} disabled={loading || !input.trim()}>➤</button>
        </div>
      </div>
    </aside>
  );
}
