import axios from 'axios';
import { mockAnalytics } from '../data/mockAnalytics';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function fetchAnalytics({ period = '7d' } = {}) {
  if (!API_BASE_URL) {
    return Promise.resolve(mockAnalytics);
  }

  const { data } = await axios.get(`${API_BASE_URL}/analytics`, {
    params: { period },
  });

  return data;
}
