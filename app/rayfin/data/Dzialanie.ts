import { entity, authenticated, uuid, text, date } from '@microsoft/rayfin-core';

// Wspólny plan działań zespołu operacji i IT, tworzony z sygnałów w aplikacji.
@entity()
@authenticated(['create', 'read', 'update', 'delete'])
export class Dzialanie {
  @uuid() id!: string;
  @text({ max: 200 }) tytul!: string;
  @text({ max: 1000, optional: true }) opis?: string;
  @text({ max: 60, optional: true }) sygnal_id?: string;
  @text({ max: 30 }) obszar!: string;
  @text({ max: 120 }) wlasciciel!: string;
  @date() termin!: Date;
  @text({ max: 20 }) status!: string;
  @text({ max: 20 }) priorytet!: string;
  @text({ max: 120 }) autor!: string;
  @text({ max: 120 }) autor_id!: string;
  @date() utworzono!: Date;
}
