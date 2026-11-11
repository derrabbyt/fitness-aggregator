/**
 * Home's read models (coach/coach-skills/schemas/web_home*.schema.json).
 * Each Home block is a part of `home` with its own schema and type; a new
 * block adds its optional key to HomeView and its type below.
 */
import { Freshness } from '../../api/types';
import { StrengthTrend } from '../../ui/strength-trend';

/** web_home.schema.json (GET /api/coach/home?day=). */
export interface HomeView {
  date: string;
  is_today: boolean;
  freshness: Freshness;
  food?: HomeFood;
  training?: HomeTraining;
  banner?: HomeBanner | null;
}

/** web_home_training.schema.json: one line per session of the day. */
export interface TrainingSession {
  type: 'lift' | 'run' | 'wrestling' | 'other';
  name: string;
  /** "HH:MM" or the plan's label (morning, midday, afternoon, evening). */
  time: string | null;
  minutes: number | null;
  distance_km: number | null;
  pace_s_per_km: number | null;
  skipped: boolean;
}

/** web_home_training.schema.json: the `training` part (Gym and Other activities blocks). */
export interface HomeTraining {
  gym: {
    sessions: TrainingSession[];
    trend: { progressing: number; counted: number; stalls: number; prs: number } | null;
    strength_trend: StrengthTrend;
  };
  other: { sessions: TrainingSession[] };
}

/** web_home_banner.schema.json: only on today, null when nothing waits. */
export interface HomeBanner {
  proposal: { id: string; type: 'calorie_change' | 'calibration_change'; change: string } | null;
  questions: number;
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
