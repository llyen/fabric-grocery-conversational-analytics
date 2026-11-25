import { useCallback, useEffect, useMemo, useState } from 'react';

import { Karta, Naglowek, Plakietka, Przycisk } from '@/components/ui';
import { useAuth } from '@/hooks/AuthContext';
import { linkRaport, zapytajAgenta } from '@/lib/fabric';
import { fData, fDataKrotka, fInt, S, type Ladowanie } from '@/lib/snapshot';
import { listaPotwierdzen, potwierdz, type PotwierdzenieRow } from '@/services/operacje';

const KOLOR_STATUSU: Record<string, string> = {
  Sukces: 'bg-green-500',
  Częściowy: 'bg-amber-500',
  Błąd: 'bg-red-500',
};

const STATUSY_INC = ['Przyjęte', 'W naprawie', 'Rozwiązane'];

function Incydent({
  l,
  historia,
  onZapis,
}: {
  l: Ladowanie;
  historia: PotwierdzenieRow[];
  onZapis: () => Promise<void>;
}) {
  const { user } = useAuth();
  const [status, setStatus] = useState(historia[0]?.status === 'Przyjęte' ? 'W naprawie' : 'Przyjęte');
  const [komentarz, setKomentarz] = useState('');
  const [zapis, setZapis] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);

  const zapisz = async () => {
    if (!user || !komentarz.trim()) return;
    setZapis(true);
    setBlad(null);
    try {
      await potwierdz(l.id, status, komentarz.trim().slice(0, 500), user);
      setKomentarz('');
      await onZapis();
    } catch (err) {
      setBlad(err instanceof Error ? err.message : 'Nie udało się zapisać.');
    } finally {
      setZapis(false);
    }
  };

  const ostatni = historia[0]?.status;
  return (
    <Karta>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium text-slate-900">{l.tabela}</span>
            <Plakietka tekst={l.status} kolor={l.status === 'Błąd' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'} />
            {ostatni && <Plakietka tekst={ostatni} kolor="bg-sky-100 text-sky-800" />}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {l.system}, dane za {fData(l.d)}, próba {l.proba}, start {l.start.replace('T', ' ')}
          </div>
        </div>
        <div className="text-right text-sm tabular-nums text-slate-700">
          {fInt(l.zal)} z {fInt(l.ocz)} wierszy
        </div>
      </div>
      {l.blad && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{l.blad}</p>}
      {historia.length > 0 && (
        <ul className="mt-3 space-y-1 border-l-2 border-sky-200 pl-3 text-xs text-slate-600">
          {historia.map((h) => (
            <li key={h.id}>
              <span className="font-medium">{h.status}</span>, {h.autor}, {h.kiedy.slice(0, 16).replace('T', ' ')}: {h.komentarz}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSY_INC.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <input
          className="min-w-48 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="Komentarz dla biznesu, np. przewidywany czas doładowania"
          value={komentarz}
          maxLength={500}
          onChange={(e) => setKomentarz(e.target.value)}
        />
        <Przycisk wariant="glowny" disabled={zapis || !komentarz.trim()} onClick={() => void zapisz()}>
          {zapis ? 'Zapisywanie...' : 'Zapisz'}
        </Przycisk>
      </div>
      {blad && <p className="mt-2 text-sm text-red-600">{blad}</p>}
    </Karta>
  );
}

export function DanePage() {
  const [potw, setPotw] = useState<PotwierdzenieRow[]>([]);
  const [blad, setBlad] = useState<string | null>(null);

  const odswiez = useCallback(async () => {
    try {
      setPotw(await listaPotwierdzen());
      setBlad(null);
    } catch (err) {
      setBlad(err instanceof Error ? err.message : 'Nie udało się pobrać potwierdzeń.');
    }
  }, []);

  useEffect(() => {
    void odswiez();
  }, [odswiez]);

  const dni = useMemo(() => [...new Set(S.ladowania.map((l) => l.d))].sort(), []);
  const tabele = useMemo(() => [...new Set(S.ladowania.map((l) => `${l.system}|${l.tabela}`))], []);
  const ostatnia = (d: string, t: string) =>
    S.ladowania.filter((l) => l.d === d && `${l.system}|${l.tabela}` === t).sort((a, b) => b.proba - a.proba)[0];
  const problemy = S.ladowania.filter((l) => l.status !== 'Sukces').sort((a, b) => b.d.localeCompare(a.d));
  const wczoraj = S.ladowania.filter((l) => l.d === S.meta.wczoraj);
  const wczorajOk = wczoraj.filter((l) => l.status === 'Sukces').length;

  return (
    <>
      <Naglowek
        tytul="Status danych (IT)"
        podtytul="Czy liczby na pulpicie można dziś pokazać zarządowi? Nocne ładowania z systemów źródłowych i kontrole jakości."
        akcje={
          <>
            <Przycisk onClick={() => void zapytajAgenta('Czy dane za wczoraj są kompletne?')}>✦ Zapytaj agenta</Przycisk>
            <Przycisk href={linkRaport('p4DaneIT')}>Raport IT ↗</Przycisk>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Karta>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Ładowania za {fDataKrotka(S.meta.wczoraj)}</div>
          <div className={`mt-2 text-3xl font-semibold ${wczorajOk < wczoraj.length ? 'text-amber-600' : 'text-green-600'}`}>
            {wczorajOk} z {wczoraj.length}
          </div>
          <div className="mt-1 text-sm text-slate-500">zakończone pełnym sukcesem</div>
        </Karta>
        <Karta>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Problemy w 14 dniach</div>
          <div className="mt-2 text-3xl font-semibold text-slate-900">{problemy.length}</div>
          <div className="mt-1 text-sm text-slate-500">ładowania ze statusem innym niż Sukces</div>
        </Karta>
        <Karta>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Kontrole jakości (cały okres)</div>
          <div className="mt-2 text-3xl font-semibold text-slate-900">{S.kontrole.length}</div>
          <div className="mt-1 text-sm text-slate-500">niezaliczone lub z ostrzeżeniem</div>
        </Karta>
      </div>

      <Karta className="mt-6 overflow-x-auto">
        <h2 className="mb-3 font-medium text-slate-900">Mapa ładowań, ostatnie 14 dni (dzień biznesowy)</h2>
        <table className="text-xs">
          <thead>
            <tr>
              <th className="pr-3 text-left font-normal text-slate-500">Tabela</th>
              {dni.map((d) => (
                <th key={d} className="px-1 font-normal text-slate-500">{fDataKrotka(d)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tabele.map((t) => (
              <tr key={t}>
                <td className="whitespace-nowrap pr-3 font-mono text-slate-700">{t.split('|')[1]}</td>
                {dni.map((d) => {
                  const l = ostatnia(d, t);
                  const proby = S.ladowania.filter((x) => x.d === d && `${x.system}|${x.tabela}` === t).length;
                  return (
                    <td key={d} className="px-1 py-1">
                      <div
                        title={l ? `${l.status}, ${fInt(l.zal)}/${fInt(l.ocz)}${proby > 1 ? `, ${proby} próby` : ''}` : 'brak'}
                        className={`mx-auto h-5 w-7 rounded ${l ? KOLOR_STATUSU[l.status] ?? 'bg-slate-300' : 'bg-slate-200'} ${proby > 1 ? 'ring-2 ring-red-400 ring-offset-1' : ''}`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-500">
          Zielony to sukces, pomarańczowy to ładowanie częściowe. Czerwona obwódka oznacza, że ładowanie wymagało ponowienia.
        </p>
      </Karta>

      <h2 className="mb-3 mt-8 font-medium text-slate-900">Incydenty do obsłużenia</h2>
      {blad && <p className="mb-3 text-sm text-red-600">{blad}</p>}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {problemy.map((l) => (
          <Incydent key={l.id} l={l} historia={potw.filter((p) => p.ladowanie_id === l.id)} onZapis={odswiez} />
        ))}
      </div>

      <Karta className="mt-6">
        <h2 className="mb-3 font-medium text-slate-900">Kontrole jakości danych, które nie przeszły</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th className="py-1 font-normal">Dzień</th>
              <th className="font-normal">Tabela</th>
              <th className="font-normal">Kontrola</th>
              <th className="font-normal">Wynik</th>
              <th className="text-right font-normal">Błędne wiersze</th>
            </tr>
          </thead>
          <tbody>
            {S.kontrole.map((k, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="py-1.5">{fData(k.d)}</td>
                <td className="font-mono text-xs">{k.tabela}</td>
                <td>{k.kontrola}</td>
                <td>
                  <Plakietka tekst={k.wynik} kolor={k.wynik === 'Niezaliczona' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'} />
                </td>
                <td className="text-right tabular-nums">{fInt(k.bledne)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Karta>
    </>
  );
}
