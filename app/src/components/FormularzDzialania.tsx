import { useState } from 'react';

import { Przycisk } from '@/components/ui';
import { useAuth } from '@/hooks/AuthContext';
import { addDays, S } from '@/lib/snapshot';
import { dodajDzialanie } from '@/services/operacje';

export interface Szkic {
  tytul: string;
  opis?: string;
  sygnal_id?: string;
  obszar: string;
  priorytet?: string;
}

const WLASCICIELE = [
  'Kierownik transportu Rzeszów',
  'Kierownik centrum Lublin',
  'Kierownik magazynu Rzeszów',
  'Zakupy, kategoria Nabiał',
  'Zespół danych (IT)',
  'Integracje TMS (IT)',
  'COO',
];

export function FormularzDzialania({
  szkic,
  onZamknij,
  onZapisano,
}: {
  szkic: Szkic;
  onZamknij: () => void;
  onZapisano: () => void;
}) {
  const { user } = useAuth();
  const [tytul, setTytul] = useState(szkic.tytul);
  const [opis, setOpis] = useState(szkic.opis ?? '');
  const [wlasciciel, setWlasciciel] = useState(szkic.obszar === 'Dane' ? 'Zespół danych (IT)' : WLASCICIELE[0]);
  const [termin, setTermin] = useState(addDays(S.meta.dzis, 7));
  const [priorytet, setPriorytet] = useState(szkic.priorytet ?? 'Wysoki');
  const [zapis, setZapis] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);

  const zapisz = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setZapis(true);
    setBlad(null);
    try {
      await dodajDzialanie(
        { tytul: tytul.slice(0, 200), opis: opis.slice(0, 1000) || undefined, sygnal_id: szkic.sygnal_id, obszar: szkic.obszar, wlasciciel, termin, priorytet },
        user
      );
      onZapisano();
    } catch (err) {
      setBlad(err instanceof Error ? err.message : 'Nie udało się zapisać działania.');
    } finally {
      setZapis(false);
    }
  };

  const pole = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onZamknij}>
      <form
        onSubmit={(e) => void zapisz(e)}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg space-y-4 rounded-2xl bg-white p-6 shadow-xl"
      >
        <h2 className="text-lg font-semibold text-slate-900">Nowe działanie</h2>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-600">Co trzeba zrobić</span>
          <input className={pole} value={tytul} onChange={(e) => setTytul(e.target.value)} required maxLength={200} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-600">Kontekst</span>
          <textarea className={pole} rows={4} value={opis} onChange={(e) => setOpis(e.target.value)} maxLength={1000} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Właściciel</span>
            <select className={pole} value={wlasciciel} onChange={(e) => setWlasciciel(e.target.value)}>
              {WLASCICIELE.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Termin</span>
            <input type="date" className={pole} value={termin} onChange={(e) => setTermin(e.target.value)} required />
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-600">Priorytet</span>
          <select className={pole} value={priorytet} onChange={(e) => setPriorytet(e.target.value)}>
            <option>Wysoki</option>
            <option>Średni</option>
            <option>Niski</option>
          </select>
        </label>
        {blad && <p className="text-sm text-red-600">{blad}</p>}
        <div className="flex justify-end gap-2">
          <Przycisk wariant="cichy" onClick={onZamknij}>Anuluj</Przycisk>
          <Przycisk wariant="glowny" type="submit" disabled={zapis}>{zapis ? 'Zapisywanie...' : 'Dodaj do planu'}</Przycisk>
        </div>
      </form>
    </div>
  );
}
