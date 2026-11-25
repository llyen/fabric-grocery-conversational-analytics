import { useState } from 'react';

import { FormularzDzialania } from '@/components/FormularzDzialania';
import { Karta, Naglowek, Plakietka, Przycisk } from '@/components/ui';
import { useDzialania } from '@/hooks/useDzialania';
import { fData, S } from '@/lib/snapshot';
import { STATUSY, usunDzialanie, zmienStatus, type DzialanieRow, type StatusDzialania } from '@/services/operacje';

const KOLOR_PRIORYTETU: Record<string, string> = {
  Wysoki: 'bg-red-100 text-red-700',
  Średni: 'bg-amber-100 text-amber-800',
  Niski: 'bg-slate-100 text-slate-700',
};

export function PlanPage() {
  const { dzialania, ladowanie, blad, odswiez } = useDzialania();
  const [nowe, setNowe] = useState(false);
  const [zajete, setZajete] = useState<string | null>(null);

  const wykonaj = async (id: string, f: () => Promise<void>) => {
    setZajete(id);
    try {
      await f();
      await odswiez();
    } finally {
      setZajete(null);
    }
  };

  const karta = (d: DzialanieRow) => {
    const idx = STATUSY.indexOf(d.status as StatusDzialania);
    const poTerminie = d.status !== 'Zrobione' && d.termin.slice(0, 10) < S.meta.dzis;
    return (
      <div key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <Plakietka tekst={d.priorytet} kolor={KOLOR_PRIORYTETU[d.priorytet]} />
          <Plakietka tekst={d.obszar} kolor="bg-indigo-50 text-indigo-800" />
        </div>
        <div className="mt-2 font-medium text-slate-900">{d.tytul}</div>
        {d.opis && <p className="mt-1 line-clamp-3 text-xs text-slate-500">{d.opis}</p>}
        <div className="mt-3 space-y-0.5 text-xs text-slate-600">
          <div>Właściciel: {d.wlasciciel}</div>
          <div className={poTerminie ? 'font-medium text-red-600' : ''}>Termin: {fData(d.termin)}</div>
          <div className="text-slate-400">Dodał(a): {d.autor}</div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {idx > 0 && (
            <Przycisk wariant="cichy" disabled={zajete === d.id} onClick={() => void wykonaj(d.id, () => zmienStatus(d.id, STATUSY[idx - 1]))}>
              ←
            </Przycisk>
          )}
          {idx < STATUSY.length - 1 && (
            <Przycisk wariant="drugi" disabled={zajete === d.id} onClick={() => void wykonaj(d.id, () => zmienStatus(d.id, STATUSY[idx + 1]))}>
              {STATUSY[idx + 1]} →
            </Przycisk>
          )}
          <Przycisk wariant="cichy" disabled={zajete === d.id} onClick={() => void wykonaj(d.id, () => usunDzialanie(d.id))}>
            Usuń
          </Przycisk>
        </div>
      </div>
    );
  };

  return (
    <>
      <Naglowek
        tytul="Plan działań"
        podtytul="Wspólna lista zadań operacji i IT. Zapisywana w bazie aplikacji w Fabric, widoczna dla wszystkich zalogowanych."
        akcje={<Przycisk wariant="glowny" onClick={() => setNowe(true)}>+ Nowe działanie</Przycisk>}
      />
      {blad && <Karta className="mb-4 border-red-200 bg-red-50 text-sm text-red-700">{blad}</Karta>}
      {ladowanie && dzialania.length === 0 ? (
        <div className="text-sm text-slate-500">Ładowanie...</div>
      ) : dzialania.length === 0 ? (
        <Karta className="text-sm text-slate-600">
          Plan jest pusty. Przejdź do zakładki Sygnały i użyj przycisku „Utwórz działanie” przy wybranym sygnale.
        </Karta>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {STATUSY.map((st) => {
            const kol = dzialania.filter((d) => d.status === st);
            return (
              <div key={st} className="rounded-2xl bg-slate-100/70 p-3">
                <div className="mb-3 flex items-center justify-between px-1 text-sm font-medium text-slate-700">
                  {st}
                  <span className="text-slate-400">{kol.length}</span>
                </div>
                <div className="space-y-3">{kol.map(karta)}</div>
              </div>
            );
          })}
        </div>
      )}
      {nowe && (
        <FormularzDzialania
          szkic={{ tytul: '', obszar: 'Dostawy' }}
          onZamknij={() => setNowe(false)}
          onZapisano={() => {
            setNowe(false);
            void odswiez();
          }}
        />
      )}
    </>
  );
}
