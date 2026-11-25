import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '@/hooks/AuthContext';
import { linkRaport, linkWorkspace } from '@/lib/fabric';
import { fData, S } from '@/lib/snapshot';

const MENU = [
  { to: '/', etykieta: 'Pulpit dnia', ikona: '◧' },
  { to: '/sygnaly', etykieta: 'Sygnały', ikona: '⚑' },
  { to: '/plan', etykieta: 'Plan działań', ikona: '☑' },
  { to: '/dane', etykieta: 'Status danych (IT)', ikona: '⛁' },
  { to: '/zapytaj', etykieta: 'Zapytaj agenta', ikona: '✦' },
];

export function Uklad() {
  const { user, signOut } = useAuth();
  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-5">
          <div className="text-lg font-semibold text-slate-900">Northwind Operacje</div>
          <div className="text-xs text-slate-500">demo na danych syntetycznych</div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {MENU.map((m) => (
            <NavLink
              key={m.to}
              to={m.to}
              end={m.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-indigo-50 font-medium text-indigo-800' : 'text-slate-600 hover:bg-slate-50'}`
              }
            >
              <span className="w-4 text-center">{m.ikona}</span>
              {m.etykieta}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-1 border-t border-slate-200 px-5 py-4 text-xs">
          <a className="block text-slate-500 hover:text-indigo-700" href={linkRaport()} target="_blank" rel="noreferrer">
            Raport Power BI ↗
          </a>
          <a className="block text-slate-500 hover:text-indigo-700" href={linkWorkspace()} target="_blank" rel="noreferrer">
            Obszar roboczy Fabric ↗
          </a>
        </div>
        <div className="border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
          <div className="truncate" title={user?.email}>{user?.name}</div>
          <button className="mt-1 text-indigo-700 hover:underline" onClick={() => void signOut()}>
            Wyloguj
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-3 text-sm">
          <span className="text-slate-600">
            Stan na {fData(S.meta.dzis)} rano. Dane operacyjne do {fData(S.meta.wczoraj)}.
          </span>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">Dane syntetyczne</span>
        </header>
        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
        <footer className="px-8 pb-6 text-xs text-slate-400">{S.meta.uwaga}</footer>
      </div>
    </div>
  );
}
