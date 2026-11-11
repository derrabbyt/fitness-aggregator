/**
 * Home's read models (coach/coach-skills/schemas/web_home*.schema.json).
 * Each Home block is a part of `home` with its own schema and type; a new
 * block adds its optional key to HomeView and its type below.
 */
import { Freshness } from '../../api/types';
import { StrengthTrend } from '../../ui/strength-trend';
import { HomeWeight } from './weight.types';

/** web_home.schema.json (GET /api/coach/home?day=). */
export interface HomeView {
  date: string;
  is_today: boolean;
  freshness: Freshness;
  food?: HomeFood;
  weight?: HomeWeight;
  steps?: HomeSteps;
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

/** A lifting session: also its PR count (null when reported done without a Hevy session). */
export interface LiftSession extends TrainingSession {
  prs: number | null;
}

/** web_home_training.schema.json: the `training` part (Workouts and Other activities cards). */
export interface HomeTraining {
  workouts: {
    sessions: LiftSession[];
    strength_trend: StrengthTrend;
    /** The last 14 days (lift_recency_days); null before any lift was trained. */
    summary: { progressing: number; counted: number; stalls: number; prs: number } | null;
  };
  other_activities: { sessions: TrainingSession[] };
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
  /** How the target is built; the parts add up to total_kcal. Null before a phase. */
  build_up: {
    base_kcal: number;
    steps_kcal: number;
    workouts_kcal: number;
    activities_kcal: number;
    surplus_kcal: number;
    total_kcal: number;
  } | null;
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
