import { useState, useEffect } from 'react';
import axiosInstance from '@shared/api/axiosConfig';

export const usePaperlessHealth = () => {
  const [isHealthy, setIsHealthy] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const { data } = await axiosInstance.get('/paperless/health/');
        if (!cancelled) setIsHealthy(!!data.is_healthy);
      } catch {
        if (!cancelled) setIsHealthy(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return { isHealthy, loading };
};
