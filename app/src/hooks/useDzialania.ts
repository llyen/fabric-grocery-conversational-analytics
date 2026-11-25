import { useCallback, useEffect, useState } from 'react';

import { useAuth } from '@/hooks/AuthContext';
import { listaDzialan, type DzialanieRow } from '@/services/operacje';

function czySesjaWygasla(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /401|unauthori[sz]ed|expired/i.test(msg);
}

export function useDzialania() {
  const { handleSessionExpired } = useAuth();
  const [dzialania, setDzialania] = useState<DzialanieRow[]>([]);
  const [ladowanie, setLadowanie] = useState(true);
  const [blad, setBlad] = useState<string | null>(null);

  const odswiez = useCallback(async () => {
    setLadowanie(true);
    try {
      setDzialania(await listaDzialan());
      setBlad(null);
    } catch (err) {
      if (czySesjaWygasla(err)) handleSessionExpired();
      setBlad(err instanceof Error ? err.message : 'Nie udało się pobrać działań.');
    } finally {
      setLadowanie(false);
    }
  }, [handleSessionExpired]);

  useEffect(() => {
    void odswiez();
  }, [odswiez]);

  return { dzialania, ladowanie, blad, odswiez };
}
