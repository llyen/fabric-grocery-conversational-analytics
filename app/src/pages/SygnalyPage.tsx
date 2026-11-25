import { useState } from 'react';

import { FormularzDzialania, type Szkic } from '@/components/FormularzDzialania';
import { Karta, Naglowek, Plakietka, Przycisk } from '@/components/ui';
import { useDzialania } from '@/hooks/useDzialania';
import { linkRaport, STRONY_RAPORTU, zapytajAgenta } from '@/lib/fabric';
import { S, type Sygnal } from '@/lib/snapshot';

const FILTRY = ['Wszystkie', 'COO', 'IT'] as const;

const PROPOZYCJE: Record<string, string> = {
  'rze-punktualnosc': 'Przesunąć część dostaw z okna 16-18 w Rzeszowie i sprawdzić trasy omijające korki',
  'pogoda-tydzien42': 'Przygotować procedurę na dni z ulewami (bufor czasu, komunikat do klientów)',
  'lublin-poranki': 'Przegląd przepustowości kompletacji porannej w centrum Lublin',
  'dostawca-braki': 'Rozmowa z Mleczarnią Dolina o poziomie realizacji dostaw',
  'rze-odpisy-0710': 'Analiza przerwy w łańcuchu chłodniczym w magazynie Rzeszów 7.10',
  'tms-2710': 'Doładować zdarzenia TMS za 27.10 dla Olsztyna i Elbląga',
  'wms-1310': 'Uzgodnić z dostawcą WMS proces zmian schematu eksportu',
};

export function SygnalyPage() {
  const [filtr, setFiltr] = useState<(typeof FILTRY)[number]>('Wszystkie');
  const [szkic, setSzkic] = useState<Szkic | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const { dzialania, odswiez } = useDzialania();

  const lista = S.sygnaly.filter((s) => filtr === 'Wszystkie' || s.odbiorca === filtr);

  const pokaz = (t: string) => {
    setToast(t);
    window.setTimeout(() => setToast(null), 4000);
  };

  const zapytaj = async (s: Sygnal) => {
    const ok = await zapytajAgenta(s.pytanie);
    pokaz(ok ? 'Pytanie skopiowane. Wklej je w oknie agenta (Ctrl+V).' : 'Otworzono agenta. Skopiuj pytanie z karty.');
  };

  return (
    <>
      <Naglowek
        tytul="Sygnały"
        podtytul="Odchylenia wykryte w danych. Każdy sygnał można dopytać u agenta, otworzyć w raporcie albo zamienić w działanie."
        akcje={FILTRY.map((f) => (
          <Przycisk key={f} wariant={f === filtr ? 'glowny' : 'drugi'} onClick={() => setFiltr(f)}>
            {f}
          </Przycisk>
        ))}
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {lista.map((s) => {
          const powiazane = dzialania.filter((d) => d.sygnal_id === s.id);
          return (
            <Karta key={s.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex flex-wrap gap-2">
                  <Plakietka tekst={s.waga} />
                  <Plakietka tekst={s.obszar} kolor="bg-indigo-50 text-indigo-800" />
                  <Plakietka tekst={s.odbiorca} kolor="bg-sky-100 text-sky-800" />
                </div>
                <div className="text-right text-2xl font-semibold text-slate-900">{s.liczba}</div>
              </div>
              <h2 className="mt-3 text-base font-semibold text-slate-900">{s.tytul}</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.opis}</p>
              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <span className="text-slate-500">Pytanie do agenta: </span>„{s.pytanie}”
              </div>
              {powiazane.length > 0 && (
                <div className="mt-3 text-xs text-slate-500">
                  W planie: {powiazane.map((d) => `${d.tytul} (${d.status})`).join('; ')}
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <Przycisk wariant="glowny" onClick={() => void zapytaj(s)}>✦ Zapytaj agenta</Przycisk>
                <Przycisk href={linkRaport(s.strona)}>Raport: {STRONY_RAPORTU[s.strona]} ↗</Przycisk>
                <Przycisk
                  onClick={() =>
                    setSzkic({
                      tytul: PROPOZYCJE[s.id] ?? s.tytul,
                      opis: `${s.tytul}. ${s.opis}`,
                      sygnal_id: s.id,
                      obszar: s.obszar,
                      priorytet: s.waga === 'wysoka' ? 'Wysoki' : s.waga === 'średnia' ? 'Średni' : 'Niski',
                    })
                  }
                >
                  + Utwórz działanie
                </Przycisk>
              </div>
            </Karta>
          );
        })}
      </div>
      {szkic && (
        <FormularzDzialania
          szkic={szkic}
          onZamknij={() => setSzkic(null)}
          onZapisano={() => {
            setSzkic(null);
            void odswiez();
            pokaz('Działanie dodane do planu.');
          }}
        />
      )}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white shadow-lg">{toast}</div>
      )}
    </>
  );
}
