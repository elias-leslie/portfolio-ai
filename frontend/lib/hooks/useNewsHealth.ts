import { useEffect, useState } from "react";
import { fetchNewsHealth, type NewsHealthResponse } from "@/lib/api/news";

export function useNewsHealth(refreshInterval: number = 60000) {
  const [data, setData] = useState<NewsHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const load = async () => {
    try {
      const result = await fetchNewsHealth();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  return { data, isLoading, error, refresh: load };
}
