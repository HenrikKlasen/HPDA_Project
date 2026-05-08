import { useState, useEffect } from 'react';

const BASE = 'http://localhost:5000';

export function useBackendPage(cacheKey, apiPath) {
  const [html, setHtml] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      setHtml(cached);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`${BASE}${apiPath}`)
      .then(res => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.text();
      })
      .then(content => {
        localStorage.setItem(cacheKey, content);
        setHtml(content);
      })
      .catch(err => {
        console.error(`Failed to load ${apiPath}:`, err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [cacheKey, apiPath]);

  function refresh() {
    localStorage.removeItem(cacheKey);
    setHtml(null);
    setLoading(true);
    setError(null);

    fetch(`${BASE}${apiPath}`)
      .then(res => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.text();
      })
      .then(content => {
        localStorage.setItem(cacheKey, content);
        setHtml(content);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }

  return { html, loading, error, refresh };
}
