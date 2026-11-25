import raw from '@/data/snapshot.json';

export interface Dzien {
  d: string;
  m: string;
  zam: number;
  pomiar: number;
  punkt: number;
  bezTms: number;
  linie: number;
  linieNk: number;
  linieBrak: number;
  wartZam: number;
  wartWyd: number;
  wartUtr: number;
  wyjOpozn: number;
}

export interface Sygnal {
  id: string;
  obszar: 'Dostawy' | 'Braki' | 'Straty' | 'Dane';
  odbiorca: 'COO' | 'IT';
  waga: 'wysoka' | 'średnia' | 'niska';
  miasto: string | null;
  tytul: string;
  liczba: string;
  opis: string;
  pytanie: string;
  strona: string;
}

export interface Ladowanie {
  id: number;
  d: string;
  system: string;
  tabela: string;
  start: string;
  min: number;
  zal: number;
  ocz: number;
  status: string;
  blad: string | null;
  proba: number;
}

export interface Kontrola {
  d: string;
  system: string;
  tabela: string;
  kontrola: string;
  wynik: string;
  bledne: number;
}

interface Snapshot {
  meta: { dzis: string; wczoraj: string; od: string; do: string; uwaga: string };
  miasta: { id: string; nazwa: string; mag: string }[];
  magazyny: { id: string; nazwa: string }[];
  przyczyny: Record<string, string>;
  przyczynyOdpisu: Record<string, string>;
  dzienne: Dzien[];
  odpisy: { d: string; mag: string; wart: number }[];
  przyczyny7: { m: string; kod: string; n: number }[];
  sygnaly: Sygnal[];
  ladowania: Ladowanie[];
  kontrole: Kontrola[];
}

export const S = raw as unknown as Snapshot;

export const nazwaMiasta = (id: string) => S.miasta.find((m) => m.id === id)?.nazwa ?? id;

export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export interface Kpi {
  zam: number;
  punktualnosc: number;
  bezTms: number;
  braki: number;
  niekompletne: number;
  utracona: number;
  odpisy: number;
  odpisyPct: number;
  wyjOpozn: number;
}

function agreguj(rows: Dzien[], odpisy: number): Kpi {
  const s = (f: (r: Dzien) => number) => rows.reduce((a, r) => a + f(r), 0);
  const pomiar = s((r) => r.pomiar);
  const linie = s((r) => r.linie);
  const wyd = s((r) => r.wartWyd);
  return {
    zam: s((r) => r.zam),
    punktualnosc: pomiar ? (100 * s((r) => r.punkt)) / pomiar : 0,
    bezTms: s((r) => r.bezTms),
    braki: linie ? (100 * s((r) => r.linieBrak)) / linie : 0,
    niekompletne: linie ? (100 * s((r) => r.linieNk)) / linie : 0,
    utracona: s((r) => r.wartUtr),
    odpisy,
    odpisyPct: wyd ? (100 * odpisy) / wyd : 0,
    wyjOpozn: s((r) => r.wyjOpozn),
  };
}

function magazynyMiast(miasta: string[] | null): Set<string> | null {
  if (!miasta) return null;
  return new Set(S.miasta.filter((m) => miasta.includes(m.id)).map((m) => m.mag));
}

/** KPI za zakres dat [od, do] włącznie, opcjonalnie dla wybranych miast. */
export function kpi(od: string, doDnia: string, miasta: string[] | null = null): Kpi {
  const rows = S.dzienne.filter((r) => r.d >= od && r.d <= doDnia && (!miasta || miasta.includes(r.m)));
  const mags = magazynyMiast(miasta);
  const odp = S.odpisy
    .filter((o) => o.d >= od && o.d <= doDnia && (!mags || mags.has(o.mag)))
    .reduce((a, o) => a + o.wart, 0);
  return agreguj(rows, odp);
}

/** Wczoraj kontra średnia dzienna z 28 poprzednich dni. */
export function wczorajVsSrednia(miasta: string[] | null = null) {
  const w = S.meta.wczoraj;
  const dzien = kpi(w, w, miasta);
  const od = addDays(w, -28);
  const ref = kpi(od, addDays(w, -1), miasta);
  return {
    dzien,
    ref: { ...ref, zam: ref.zam / 28, utracona: ref.utracona / 28, odpisy: ref.odpisy / 28, wyjOpozn: ref.wyjOpozn / 28, bezTms: ref.bezTms / 28 },
  };
}

/** Tygodnie (poniedziałek) z punktualnością dla miasta lub całej sieci. */
export function trendTygodniowy(miasto: string | null) {
  const tyg = new Map<string, { pomiar: number; punkt: number }>();
  for (const r of S.dzienne) {
    if (miasto && r.m !== miasto) continue;
    const d = new Date(`${r.d}T00:00:00Z`);
    const pon = addDays(r.d, -((d.getUTCDay() + 6) % 7));
    const t = tyg.get(pon) ?? { pomiar: 0, punkt: 0 };
    t.pomiar += r.pomiar;
    t.punkt += r.punkt;
    tyg.set(pon, t);
  }
  return [...tyg.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([pon, t]) => ({ pon, wartosc: t.pomiar ? (100 * t.punkt) / t.pomiar : 0 }));
}

export function punktualnoscMiast(od: string, doDnia: string) {
  return S.miasta
    .map((m) => ({ id: m.id, nazwa: m.nazwa, ...kpi(od, doDnia, [m.id]) }))
    .sort((a, b) => a.punktualnosc - b.punktualnosc);
}

export function przyczyny7(miasto: string | null) {
  const map = new Map<string, number>();
  for (const p of S.przyczyny7) if (!miasto || p.m === miasto) map.set(p.kod, (map.get(p.kod) ?? 0) + p.n);
  return [...map.entries()]
    .map(([kod, n]) => ({ kod, nazwa: S.przyczyny[kod] ?? kod, n }))
    .sort((a, b) => b.n - a.n);
}

// ------------------------------------------------------------------ formatowanie
const nf1 = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf0 = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 });

export const fPct = (x: number, n: 1 | 2 = 1) => `${(n === 2 ? nf2 : nf1).format(x)}%`;
export const fZl = (x: number) => `${nf0.format(x)} zł`;
export const fInt = (x: number) => nf0.format(x);
export const fData = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}.${m}.${y}`;
};
export const fDataKrotka = (iso: string) => {
  const [, m, d] = iso.slice(0, 10).split('-');
  return `${d}.${m}`;
};
