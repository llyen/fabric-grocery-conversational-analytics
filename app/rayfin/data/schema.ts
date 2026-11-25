import { Dzialanie } from './Dzialanie.js';
import { Potwierdzenie } from './Potwierdzenie.js';

export type AppSchema = {
  Dzialanie: Dzialanie;
  Potwierdzenie: Potwierdzenie;
};

export const schema = [Dzialanie, Potwierdzenie];
