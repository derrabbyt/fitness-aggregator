/**
 * Home's read models (coach/coach-skills/schemas/web_home*.schema.json).
 * Each Home block is a part of `home` with its own schema and type; a new
 * block adds its optional key to HomeView and its type below.
 */
import { Freshness } from '../../api/types';
import { HomeWeight } from './weight.types';

/** web_home.schema.json (GET /api/coach/home?day=). */
export interface HomeView {
  date: string;
  is_today: boolean;
  freshness: Freshness;
  food?: HomeFood;
  weight?: HomeWeight;
}

export type Logged = 'complete' | 'partial' | 'missing';

export interface MacroValue {
  eaten_g: number | null;
  target_g: number | null;
}

/** web_home_food.schema.json: the `food` part. Targets are null before a phase. */
export interface HomeFood {
  kcal: { eaten: number | null; target: number | null; left: number | null };
  logged: Logged;
  macros: {
    protein: MacroValue;
    carbs: MacroValue;
    fat: MacroValue;
    /** target_g is the low end of the fiber range. */
    fiber: MacroValue & { target_max_g: number | null };
  };
}

/** web_home_food_detail.schema.json (GET /api/coach/home/food?day=): the check-in week so far. */
export interface FoodDetail {
  date: string;
  start: string;
  end: string;
  iso_week: string;
  days: { date: string; eaten_kcal: number | null; target_kcal: number | null; logged: Logged }[];
  so_far: { days_logged: number; eaten_kcal: number | null; target_kcal: number | null; deviation_pct: number | null };
}
