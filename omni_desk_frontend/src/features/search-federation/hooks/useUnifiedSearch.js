import { useState, useCallback } from 'react';
import { unifiedSearch } from '../api/searchApi';

/**
 * 统一联邦搜索 hook。
 *
 * @returns {{
 *   results: Array,
 *   degraded: boolean,
 *   loading: boolean,
 *   search: (query: string) => Promise<void>,
 * }}
 */
export const useUnifiedSearch = () => {
  const [results, setResults] = useState([]);
  const [degraded, setDegraded] = useState(false);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (query) => {
    if (!query || !query.trim()) {
      setResults([]);
      setDegraded(false);
      return;
    }
    setLoading(true);
    try {
      const data = await unifiedSearch(query);
      setResults(data.results || []);
      setDegraded(!!data.degraded);
    } catch {
      setResults([]);
      setDegraded(false);
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, degraded, loading, search };
};
