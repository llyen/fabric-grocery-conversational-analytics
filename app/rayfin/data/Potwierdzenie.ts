import { entity, authenticated, uuid, text, int, date } from '@microsoft/rayfin-core';

// Przyjęcie incydentu ładowania danych przez IT, z komentarzem dla biznesu.
@entity()
@authenticated(['create', 'read', 'update', 'delete'])
export class Potwierdzenie {
  @uuid() id!: string;
  @int() ladowanie_id!: number;
  @text({ max: 20 }) status!: string;
  @text({ max: 500 }) komentarz!: string;
  @text({ max: 120 }) autor!: string;
  @text({ max: 120 }) autor_id!: string;
  @date() kiedy!: Date;
}
