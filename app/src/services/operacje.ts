import type { AuthUser } from './IAuthService';
import { getRayfinClient } from './rayfinClient';

export const STATUSY = ['Do zrobienia', 'W toku', 'Zrobione'] as const;
export type StatusDzialania = (typeof STATUSY)[number];

export interface DzialanieRow {
  id: string;
  tytul: string;
  opis?: string;
  sygnal_id?: string;
  obszar: string;
  wlasciciel: string;
  termin: string;
  status: string;
  priorytet: string;
  autor: string;
  utworzono: string;
}

export interface NoweDzialanie {
  tytul: string;
  opis?: string;
  sygnal_id?: string;
  obszar: string;
  wlasciciel: string;
  termin: string;
  priorytet: string;
}

export interface PotwierdzenieRow {
  id: string;
  ladowanie_id: number;
  status: string;
  komentarz: string;
  autor: string;
  kiedy: string;
}

const iso = (v: unknown) => (v instanceof Date ? v.toISOString() : String(v ?? ''));

export async function listaDzialan(): Promise<DzialanieRow[]> {
  const rows = await getRayfinClient()
    .data.Dzialanie.select([
      'id', 'tytul', 'opis', 'sygnal_id', 'obszar', 'wlasciciel', 'termin', 'status', 'priorytet', 'autor', 'utworzono',
    ])
    .orderBy({ termin: 'asc' })
    .execute();
  return rows.map((r) => ({ ...r, termin: iso(r.termin), utworzono: iso(r.utworzono) }) as DzialanieRow);
}

export async function dodajDzialanie(d: NoweDzialanie, user: AuthUser): Promise<void> {
  await getRayfinClient().data.Dzialanie.create({
    ...d,
    termin: new Date(`${d.termin}T12:00:00Z`),
    status: 'Do zrobienia',
    autor: user.name,
    autor_id: user.id,
    utworzono: new Date(),
  });
}

export async function zmienStatus(id: string, status: StatusDzialania): Promise<void> {
  await getRayfinClient().data.Dzialanie.update({ id }, { status });
}

export async function usunDzialanie(id: string): Promise<void> {
  await getRayfinClient().data.Dzialanie.delete({ id });
}

export async function listaPotwierdzen(): Promise<PotwierdzenieRow[]> {
  const rows = await getRayfinClient()
    .data.Potwierdzenie.select(['id', 'ladowanie_id', 'status', 'komentarz', 'autor', 'kiedy'])
    .orderBy({ kiedy: 'desc' })
    .execute();
  return rows.map((r) => ({ ...r, kiedy: iso(r.kiedy) }) as PotwierdzenieRow);
}

export async function potwierdz(
  ladowanieId: number,
  status: string,
  komentarz: string,
  user: AuthUser
): Promise<void> {
  await getRayfinClient().data.Potwierdzenie.create({
    ladowanie_id: ladowanieId,
    status,
    komentarz,
    autor: user.name,
    autor_id: user.id,
    kiedy: new Date(),
  });
}
