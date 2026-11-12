/** web_setup_training_plan.schema.json (GET setup/training-plan) and its commands. */

export type PlanWeekday = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';
export type SessionType = 'lift' | 'run' | 'wrestling' | 'other';
export type KcalSource = 'reported' | 'estimated' | 'model_estimate' | null;

export interface PlanSession {
  id: string;
  /** HH:MM, morning, midday, afternoon, evening, or null. */
  time: string | null;
  name: string;
  type: SessionType;
  optional: boolean;
}

export interface WeekSession extends PlanSession {
  status: 'skipped' | 'done' | null;
  kcal: number | null;
  kcal_source: KcalSource;
}

export interface ExtraSession {
  extra_id: string;
  type: SessionType;
  name: string | null;
  kcal: number | null;
  kcal_source: KcalSource;
}

export interface WeekDay {
  date: string;
  weekday: PlanWeekday;
  today: boolean;
  sessions: WeekSession[];
  extras: ExtraSession[];
}

export interface TrainingPlanView {
  editable: boolean;
  valid_from: string | null;
  upcoming: { valid_from: string }[];
  days: { weekday: PlanWeekday; sessions: PlanSession[] }[];
  this_week: WeekDay[];
  activities: string[];
}

/** POST setup/training-plan/day: a lasting change to one weekday ([] = rest day). */
export interface DayChange {
  weekday: PlanWeekday;
  sessions: { name: string; type: SessionType; time: string | null; optional: boolean }[];
  from?: string;
}

/** POST setup/training-plan/session: one report for a day of this week. */
export interface SessionReport {
  date: string;
  status: 'skipped' | 'done' | 'extra' | 'clear';
  session_id?: string;
  extra_id?: string;
  type?: SessionType;
  name?: string;
  kcal?: number;
  activity?: string;
  duration_min?: number;
}

export interface SessionResult {
  reported: {
    kcal: number | null;
    kcal_source: KcalSource;
    kcal_counted: number | null;
    estimate?: { activity: string; met: number; trend_weight_kg: number; duration_min: number };
  } | null;
  section: TrainingPlanView;
}

export const TYPE_NAMES: Record<SessionType, string> = {
  lift: 'Lifting', run: 'Run', wrestling: 'Wrestling', other: 'Other',
};
