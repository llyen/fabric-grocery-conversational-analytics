import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { KafelKpi, Karta, Linia, Naglowek, Plakietka, Przycisk, Slupki } from '@/components/ui';
import { linkRaport } from '@/lib/fabric';
import {
  addDays,
  fDataKrotka,
  fInt,
  fPct,
  fZl,
  nazwaMiasta,
  przyczyny7,
  punktualnoscMiast,
  S,
  trendTygodniowy,
  wczorajVsSrednia,
} from '@/lib/snapshot';

const TYDZ_OD = '2026-10-19';
const TYDZ_DO = '2026-10-25';

function roznica(v: number, ref: number, jednostka: 'pp' | 'pct' | 'zl' | 'szt') {
  const d = v - ref;
  const znak = d > 0 ? '+' : d < 0 ? '−' : '';
  const a = Math.abs(d);
  const txt =
    jednostka === 'pp'
      ? `${znak}${fPct(a).replace('%', ' pp')}`
      : jednostka === 'pct'
        ? `${znak}${fPct(a, 2).replace('%', ' pp')}`
        : jednostka === 'zl'
          ? `${znak}${fZl(a)}`
          : `${znak}${fInt(a)}`;
  return { d, txt };
}

export function PulpitPage() {
  const [miasto, setMiasto] = useState<string | null>(null);
  const filtr = miasto ? [miasto] : null;
  const { dzien, ref } = useMemo(() => wczorajVsSrednia(filtr), [miasto]); // eslint-disable-line react-hooks/exhaustive-deps
  const trend = useMemo(() => trendTygodniowy(miasto), [miasto]);
  const ranking = useMemo(() => punktualnoscMiast(TYDZ_OD, TYDZ_DO), []);
  const przyczyny = useMemo(() => przyczyny7(miasto), [miasto]);
  const top = S.sygnaly.filter((s) => s.waga === 'wysoka' && (!miasto || !s.miasto || s.miasto === miasto)).slice(0, 3);

  const rP = roznica(dzien.punktualnosc, ref.punktualnosc, 'pp');
  const rB = roznica(dzien.braki, ref.braki, 'pct');
  const rO = roznica(dzien.odpisy, ref.odpisy, 'zl');
  const rZ = roznica(dzien.zam, ref.zam, 'szt');
  const rW = roznica(dzien.wyjOpozn, ref.wyjOpozn, 'szt');
  const deszcz = trend.findIndex((t) => t.pon === '2026-10-12');
  const zator = trend.findIndex((t) => t.pon === '2026-09-28');

  return (
    <>
      <Naglowek
        tytul="Pulpit dnia"
        podtytul={`Wczoraj (${fDataKrotka(S.meta.wczoraj)}) wobec średniej dziennej z 28 dni (${fDataKrotka(addDays(S.meta.wczoraj, -28))}-${fDataKrotka(addDays(S.meta.wczoraj, -1))})`}
        akcje={
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
            value={miasto ?? ''}
            onChange={(e) => setMiasto(e.target.value || null)}
          >
            <option value="">Cała sieć</option>
            {S.miasta.map((m) => (
              <option key={m.id} value={m.id}>{m.nazwa}</option>
            ))}
          </select>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KafelKpi etykieta="Zamówienia" wartosc={fInt(dzien.zam)} porownanie={`${rZ.txt} wobec średniej`} />
        <KafelKpi
          etykieta="Punktualność"
          wartosc={fPct(dzien.punktualnosc)}
          porownanie={`${rP.txt} wobec ${fPct(ref.punktualnosc)}`}
          delta={rP.d}
          lepiejWyzej
          uwaga={dzien.bezTms > 0 ? `${fInt(dzien.bezTms)} zamówień bez danych z TMS, liczone bez nich` : undefined}
        />
        <KafelKpi
          etykieta="Udział braków"
          wartosc={fPct(dzien.braki, 2)}
          porownanie={`${rB.txt} wobec ${fPct(ref.braki, 2)}`}
          delta={rB.d}
        />
        <KafelKpi etykieta="Odpisy" wartosc={fZl(dzien.odpisy)} porownanie={`${rO.txt} wobec średniej`} delta={rO.d} />
        <KafelKpi
          etykieta="Opóźnione wyjazdy"
          wartosc={fInt(dzien.wyjOpozn)}
          porownanie={`${rW.txt} wobec średniej (> 15 min)`}
          delta={rW.d}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Karta className="xl:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-medium text-slate-900">
              Punktualność tydzień do tygodnia, {miasto ? nazwaMiasta(miasto) : 'cała sieć'}
            </h2>
            <Przycisk wariant="cichy" href={linkRaport('p1Punktualnosc')}>Raport ↗</Przycisk>
          </div>
          <Linia
            punkty={trend.map((t) => t.wartosc)}
            etykiety={trend.map((t) => fDataKrotka(t.pon))}
            min={Math.min(80, ...trend.map((t) => t.wartosc))}
            max={100}
            format={(v) => fPct(v, 1)}
            wyroznij={[deszcz, zator].filter((i) => i >= 0)}
          />
          <p className="mt-2 text-xs text-slate-500">
            Czerwone punkty to tydzień zatoru w centrum Lublin (od 28.09) i deszczowy tydzień od 12.10. Ostatni tydzień jest niepełny.
          </p>
        </Karta>
        <Karta>
          <h2 className="mb-3 font-medium text-slate-900">Punktualność miast, tydzień 19-25.10</h2>
          <Slupki
            dane={ranking.map((r) => ({ etykieta: r.nazwa, wartosc: r.punktualnosc }))}
            format={(v) => fPct(v)}
            wyroznij={ranking[0]?.nazwa}
          />
        </Karta>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Karta>
          <h2 className="mb-3 font-medium text-slate-900">Przyczyny spóźnień, ostatnie 7 dni</h2>
          <Slupki dane={przyczyny.map((p) => ({ etykieta: p.nazwa, wartosc: p.n }))} format={fInt} kolor="bg-amber-500" />
        </Karta>
        <Karta className="xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-medium text-slate-900">Najważniejsze sygnały</h2>
            <Link to="/sygnaly" className="text-sm text-indigo-700 hover:underline">Wszystkie sygnały →</Link>
          </div>
          <div className="space-y-3">
            {top.map((s) => (
              <div key={s.id} className="flex items-start gap-4 rounded-xl border border-slate-100 p-3">
                <div className="w-24 shrink-0 text-xl font-semibold text-slate-900">{s.liczba}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-900">{s.tytul}</span>
                    <Plakietka tekst={s.odbiorca} kolor="bg-sky-100 text-sky-800" />
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-600">{s.opis}</p>
                </div>
              </div>
            ))}
          </div>
        </Karta>
      </div>
    </>
  );
}
