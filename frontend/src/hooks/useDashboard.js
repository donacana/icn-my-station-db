import { useCallback, useEffect, useRef, useState } from 'react';
import { getDashboardData } from '../services/dashboardService.js';

export function useDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const request = useRef(0);
  const refresh = useCallback(async () => {
    const id = ++request.current;
    setLoading(true);
    setError(null);
    try {
      const next = await getDashboardData();
      if (id === request.current) setData(next);
    } catch {
      if (id === request.current) setError('데이터를 불러오지 못했습니다. 다시 시도해 주세요.');
    } finally {
      if (id === request.current) setLoading(false);
    }
  }, []);
  useEffect(() => { refresh(); return () => { request.current += 1; }; }, [refresh]);
  return { data, loading, error, refresh };
}

