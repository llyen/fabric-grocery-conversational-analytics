// Identyfikatory raportu i agenta ustawiasz w app/.env (wzór w app/.env.example).
const WS = import.meta.env.VITE_NORTHWIND_WORKSPACE_ID || import.meta.env.VITE_FABRIC_WORKSPACE_ID || '<WORKSPACE_ID>';
const REPORT = import.meta.env.VITE_NORTHWIND_REPORT_ID || '<REPORT_ID>';
const AGENT = import.meta.env.VITE_NORTHWIND_AGENT_ID || '<DATA_AGENT_ID>';
const PORTAL = 'https://app.fabric.microsoft.com';

export const linkRaport = (strona?: string) =>
  `${PORTAL}/groups/${WS}/reports/${REPORT}${strona ? `/${strona}` : ''}?experience=fabric-developer`;

export const linkAgent = () => `${PORTAL}/groups/${WS}/aiskills/${AGENT}?experience=fabric-developer`;

export const linkWorkspace = () => `${PORTAL}/groups/${WS}/list?experience=fabric-developer`;

export const STRONY_RAPORTU: Record<string, string> = {
  p1Punktualnosc: 'Punktualność',
  p2Braki: 'Braki i zamienniki',
  p3Straty: 'Straty świeżych',
  p4DaneIT: 'Świeżość danych (IT)',
};

/** Kopiuje pytanie do schowka i otwiera agenta danych w portalu Fabric w nowej karcie. */
export async function zapytajAgenta(pytanie: string): Promise<boolean> {
  let skopiowano = false;
  try {
    await navigator.clipboard.writeText(pytanie);
    skopiowano = true;
  } catch {
    skopiowano = false;
  }
  window.open(linkAgent(), '_blank', 'noopener');
  return skopiowano;
}
