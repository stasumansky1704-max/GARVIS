// =============================================================================
// useApi — Hook for API calls with loading/error states
// =============================================================================

import { useState, useEffect, useCallback, useRef } from "react";

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(fetchFn: () => Promise<T>, deps: unknown[] = []): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const fetch = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchFn()
      .then((result) => {
        if (mounted.current) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted.current) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mounted.current = true;
    fetch();
    return () => { mounted.current = false; };
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useLazyApi<T>() {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback((fetchFn: () => Promise<T>) => {
    setLoading(true);
    setError(null);
    return fetchFn()
      .then((result) => {
        setData(result);
        setLoading(false);
        return result;
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setLoading(false);
        throw err;
      });
  }, []);

  return { data, loading, error, execute };
}
