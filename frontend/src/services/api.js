const API_BASE = '/api/v1';

async function post(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  recommend: (payload) => post('/recommend', payload),
  quickSearch: (payload) => post('/search/quick', payload),
  substitutions: (payload) => post('/substitutions', payload),
  chat: (message, context = '') => post('/chat', { message, context }),
};
