// =============================================================================
// usePolling — Fallback polling hook when WebSocket unavailable
// =============================================================================

import { useState, useEffect, useRef, useCallback } from "react";

interface UsePollingOptions<T> {
  interval?: number;
  enabled?: boolean;
  onError?: (err: Error) => void;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  options: UsePollingOptions<T> = {}
) {
  const { interval = 5000, enabled = true, onError } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mounted = useRef(true);

  const tick = useCallback(() => {
    fetchFn()
      .then((result) => {
        if (mounted.current) {
          setData(result);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted.current) {
          const msg = err instanceof Error ? err.message : String(err);
          setError(msg);
          setLoading(false);
          onError?.(err);
        }
      });
  }, [fetchFn, onError]);

  useEffect(() => {
    mounted.current = true;
    if (enabled) {
      tick();
      timerRef.current = setInterval(tick, interval);
    }
    return () => {
      mounted.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [enabled, interval, tick]);

  return { data, loading, error };
}
