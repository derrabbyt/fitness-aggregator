/**
 * Home's read models (coach/coach-skills/schemas/web_home*.schema.json).
 * Each Home block is a part of `home` with its own schema and type; a new
 * block adds its optional key to HomeView and its type below.
 */
import { Freshness } from '../../api/types';

/** web_home.schema.json (GET /api/coach/home?day=). */
export interface HomeView {
  date: string;
  is_today: boolean;
  freshness: Freshness;
  food?: HomeFood;
  steps?: HomeSteps;
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

/**
 * web_home_steps.schema.json: the `steps` part. Not tracked (under the
 * not-tracked limit): steps, to_go and kcal are null. kcal is the step part
 * of the day's target vs the goal (null before a phase).
 */
export interface HomeSteps {
  tracked: boolean;
  steps: number | null;
  goal: number;
  to_go: number | null;
  kcal: number | null;
  run_steps_removed: number;
  provisional: boolean;
}

/** web_home_steps_detail.schema.json (GET /api/coach/home/steps?day=): the 14 days ending on the day. */
export interface StepsDetail {
  date: string;
  goal: number;
  days: { date: string; tracked: boolean; steps: number | null; kcal: number | null; run_steps_removed: number }[];
  average_steps: number | null;
  days_tracked: number;
  days_at_goal: number;
}
