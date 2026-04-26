import { useEffect, useState } from 'react';
import { fetchAnalytics } from '../services/analyticsApi';

export function useAnalyticsData(period) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const response = await fetchAnalytics({ period });
        if (!ignore) setData(response);
      } catch {
        if (!ignore) setError('Unable to load analytics data.');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, [period]);

  return { data, loading, error };
}
