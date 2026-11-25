import { useState } from 'react';

import { Karta, Naglowek, Przycisk } from '@/components/ui';
import { linkAgent, zapytajAgenta } from '@/lib/fabric';

const PYTANIA: { grupa: string; opis: string; pytania: string[] }[] = [
  {
    grupa: 'COO: dostawy',
    opis: 'Punktualność, okna, przyczyny spóźnień',
    pytania: [
      'Które miasto miało najniższą punktualność w zeszłym tygodniu?',
      'W których oknach Rzeszów spóźnia się najczęściej i z jakiego powodu?',
      'Dlaczego pod koniec września spadła punktualność porannych dostaw z centrum Lublin?',
      'Jak zmieniała się punktualność tydzień do tygodnia w październiku i co ją obniżyło w tygodniu 12-18.10?',
    ],
  },
  {
    grupa: 'COO: braki i straty',
    opis: 'Dostawcy, kategorie, odpisy świeżych',
    pytania: [
      'Którzy dostawcy mieli najwyższy udział braków w październiku?',
      'Ile odpisaliśmy w magazynie w Rzeszowie 7 października i dlaczego?',
      'Jaki był udział odpisów w sprzedaży w każdym magazynie w październiku?',
    ],
  },
  {
    grupa: 'IT: dane',
    opis: 'Kompletność ładowań, kontrole jakości',
    pytania: [
      'Czy dane za wczoraj są kompletne?',
      'Które kontrole jakości danych nie przeszły w ostatnich 7 dniach?',
      'Które ładowania wymagały ponowienia w październiku i dlaczego?',
    ],
  },
];

export function ZapytajPage() {
  const [ostatnie, setOstatnie] = useState<string | null>(null);

  const zapytaj = async (p: string) => {
    await zapytajAgenta(p);
    setOstatnie(p);
  };

  return (
    <>
      <Naglowek
        tytul="Zapytaj agenta"
        podtytul="Agent danych Fabric odpowiada na pytania w języku naturalnym, korzystając z modelu semantycznego i lakehouse."
        akcje={<Przycisk wariant="glowny" href={linkAgent()}>Otwórz agenta ↗</Przycisk>}
      />
      <Karta className="mb-6 text-sm text-slate-600">
        Kliknięcie pytania kopiuje je do schowka i otwiera agenta w portalu Fabric w nowej karcie. Wklej pytanie (Ctrl+V) i wyślij.
        Agent działa w portalu Fabric, bo aplikacja nie może wywoływać go bezpośrednio z przeglądarki.
      </Karta>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {PYTANIA.map((g) => (
          <Karta key={g.grupa}>
            <h2 className="font-medium text-slate-900">{g.grupa}</h2>
            <p className="mb-3 text-xs text-slate-500">{g.opis}</p>
            <div className="space-y-2">
              {g.pytania.map((p) => (
                <button
                  key={p}
                  onClick={() => void zapytaj(p)}
                  className={`block w-full rounded-lg border px-3 py-2 text-left text-sm transition hover:border-indigo-400 hover:bg-indigo-50 ${ostatnie === p ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200'}`}
                >
                  {p}
                  {ostatnie === p && <span className="mt-1 block text-xs text-indigo-700">Skopiowano, wklej w oknie agenta</span>}
                </button>
              ))}
            </div>
          </Karta>
        ))}
      </div>
    </>
  );
}
