/**
 * The Training tab's read model (coach/coach-skills/schemas/web_training.schema.json)
 * and the strength trend (web_strength_trend.schema.json, also on Home's Gym block).
 */
import { Freshness } from '../../api/types';

/** web_strength_trend.schema.json: mean % change of the counting lifts' estimated 1RM. */
export interface StrengthTrend {
  days: number;
  band_pct: number;
  change_pct: number | null;
  direction: 'rising' | 'flat' | 'falling' | null;
  lifts: number;
  points: { week: string; start: string; change_pct: number | null }[];
}

export type LiftStatus =
  | 'progressing' | 'same' | 'declining' | 'stall' | 'paused' | 'new_baseline' | 'not_judged' | 'not_recent';

export interface TopSet {
  load_kg: number;
  reps: number;
  effective_load_kg: number;
  e1rm_kg: number;
}

export interface TrainingLift {
  exercise_id: string;
  name: string;
  status: LiftStatus;
  not_judged_reason: 'after_break' | 'building_baseline' | null;
  bodyweight_exercise: boolean;
  last_session_date: string | null;
  latest: TopSet | null;
  series: { date: string; e1rm_kg: number }[];
}

export interface TrainingActivity {
  date: string;
  type: 'run' | 'wrestling' | 'lift' | 'other';
  name: string | null;
  /** planned: counts without a report (wrestling); shown like a done one. */
  status: 'done' | 'planned' | 'skipped';
  distance_km: number | null;
  minutes: number | null;
  kcal_counted: number | null;
}

/** web_training.schema.json (GET /api/coach/training?day=). */
export interface TrainingView {
  date: string;
  freshness: Freshness;
  strength_trend: StrengthTrend;
  lifts: TrainingLift[];
  not_counted: TrainingLift[];
  activities: TrainingActivity[];
}
