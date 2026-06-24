import { useState, useEffect, useCallback } from 'react';
import { api, StatusInfo } from '@/lib/api';

export function useProjectPolling(projectId: number, enabled: boolean = true) {
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    if (!enabled) return;
    try {
      const s = await api.getProjectStatus(projectId);
      setStatus(s);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, [projectId, enabled]);

  useEffect(() => {
    if (!enabled) return;
    poll(); // immediate first fetch
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [poll, enabled]);

  return { status, error };
}
