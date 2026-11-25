import type { ReactNode } from 'react';

export function Karta({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>{children}</div>;
}

export function Naglowek({ tytul, podtytul, akcje }: { tytul: string; podtytul?: string; akcje?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{tytul}</h1>
        {podtytul && <p className="mt-1 text-sm text-slate-500">{podtytul}</p>}
      </div>
      {akcje && <div className="flex flex-wrap gap-2">{akcje}</div>}
    </div>
  );
}

const WAGA_KOLOR: Record<string, string> = {
  wysoka: 'bg-red-100 text-red-700',
  średnia: 'bg-amber-100 text-amber-800',
  niska: 'bg-slate-100 text-slate-700',
};

export function Plakietka({ tekst, kolor }: { tekst: string; kolor?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${kolor ?? WAGA_KOLOR[tekst] ?? 'bg-slate-100 text-slate-700'}`}>
      {tekst}
    </span>
  );
}

export function Przycisk({
  children,
  onClick,
  wariant = 'drugi',
  href,
  disabled,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  wariant?: 'glowny' | 'drugi' | 'cichy';
  href?: string;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  const cls = {
    glowny: 'bg-indigo-600 text-white hover:bg-indigo-700',
    drugi: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
    cichy: 'text-slate-600 hover:bg-slate-100',
  }[wariant];
  const base = `inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${cls}`;
  if (href)
    return (
      <a className={base} href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  return (
    <button type={type} className={base} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

/** Kafel KPI z porównaniem do punktu odniesienia. lepiejWyzej określa kierunek koloru. */
export function KafelKpi({
  etykieta,
  wartosc,
  porownanie,
  delta,
  lepiejWyzej,
  uwaga,
}: {
  etykieta: string;
  wartosc: string;
  porownanie?: string;
  delta?: number;
  lepiejWyzej?: boolean;
  uwaga?: string;
}) {
  let kolor = 'text-slate-500';
  if (delta !== undefined && Math.abs(delta) > 1e-9) {
    const dobrze = lepiejWyzej ? delta > 0 : delta < 0;
    kolor = dobrze ? 'text-green-600' : 'text-red-600';
  }
  return (
    <Karta>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{etykieta}</div>
      <div className="mt-2 text-3xl font-semibold text-slate-900">{wartosc}</div>
      {porownanie && <div className={`mt-1 text-sm ${kolor}`}>{porownanie}</div>}
      {uwaga && <div className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-800">{uwaga}</div>}
    </Karta>
  );
}

/** Prosty wykres liniowy SVG, bez zależności. */
export function Linia({
  punkty,
  etykiety,
  min,
  max,
  format,
  wyroznij,
}: {
  punkty: number[];
  etykiety: string[];
  min?: number;
  max?: number;
  format: (v: number) => string;
  wyroznij?: number[];
}) {
  const W = 640, H = 200, P = 32;
  const lo = min ?? Math.min(...punkty);
  const hi = max ?? Math.max(...punkty);
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, punkty.length - 1);
  const y = (v: number) => H - P - ((v - lo) * (H - 2 * P)) / Math.max(1e-9, hi - lo);
  const d = punkty.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      {[lo, (lo + hi) / 2, hi].map((v) => (
        <g key={v}>
          <line x1={P} x2={W - P} y1={y(v)} y2={y(v)} stroke="#e2e8f0" />
          <text x={2} y={y(v) + 4} fontSize="10" fill="#64748b">{format(v)}</text>
        </g>
      ))}
      <path d={d} fill="none" stroke="#4f46e5" strokeWidth={2.5} />
      {punkty.map((v, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(v)} r={wyroznij?.includes(i) ? 5 : 3} fill={wyroznij?.includes(i) ? '#dc2626' : '#4f46e5'} />
          <text x={x(i)} y={H - 8} fontSize="10" textAnchor="middle" fill="#64748b">{etykiety[i]}</text>
        </g>
      ))}
    </svg>
  );
}

/** Poziome słupki z etykietą i wartością. */
export function Slupki({
  dane,
  format,
  kolor = 'bg-indigo-500',
  wyroznij,
}: {
  dane: { etykieta: string; wartosc: number }[];
  format: (v: number) => string;
  kolor?: string;
  wyroznij?: string;
}) {
  const max = Math.max(...dane.map((d) => d.wartosc), 1e-9);
  return (
    <div className="space-y-2">
      {dane.map((d) => (
        <div key={d.etykieta} className="flex items-center gap-3 text-sm">
          <div className="w-40 shrink-0 truncate text-slate-700">{d.etykieta}</div>
          <div className="h-4 flex-1 rounded bg-slate-100">
            <div
              className={`h-4 rounded ${d.etykieta === wyroznij ? 'bg-red-500' : kolor}`}
              style={{ width: `${(100 * d.wartosc) / max}%` }}
            />
          </div>
          <div className="w-16 shrink-0 text-right tabular-nums text-slate-900">{format(d.wartosc)}</div>
        </div>
      ))}
    </div>
  );
}
