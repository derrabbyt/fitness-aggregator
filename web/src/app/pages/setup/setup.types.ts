/**
 * Setup's read models (coach/coach-skills/schemas/web_setup*.schema.json).
 * A section is a part of `setup` with a one-line summary; a section the coach
 * doesn't send yet shows as coming soon (see setup-sections.ts).
 */

/** web_setup_summary.schema.json */
export interface SectionSummary {
  summary: string;
}

/** web_setup.schema.json: the envelope plus one part per section key. */
export interface SetupView {
  phase_active: boolean;
  setup_open: boolean;
  [section: string]: SectionSummary | boolean | undefined;
}

/** web_setup_phase_targets.schema.json */
export interface PhaseTargetsView {
  phase: { phase_id: string; name: string; start_date: string; week: number | null } | null;
  targets: {
    valid_from: string;
    base_maintenance_kcal: number;
    avg_day_steps: number | null;
    base_at_step_goal_kcal: number;
    surplus_kcal: number;
    avg_daily_target_kcal: number;
    mfp_goal_kcal: number;
    at_step_goal: { rest: number; lifting: number; wrestling: number };
    today: { kcal: number; protein_g: number; carbs_g: number; fat_g: number } | null;
  } | null;
  step_goal: Range & { value: number; default: number; editable: boolean };
}

/** web_setup_messaging.schema.json */
export interface MessagingView {
  editable: boolean;
  weekly_checkin: { day: Weekday; time: string } | null;
  evening_reminder_time: string | null;
  max_unprompted_messages_per_day: number | null;
  soft_floor_min_days: number | null;
}

export type MessagingField = 'weekly_checkin' | 'evening_reminder_time' | 'max_unprompted_messages_per_day'
  | 'soft_floor_min_days';

export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

/** web_setup_activity.schema.json */
export interface ActivityView {
  editable: boolean;
  values: Record<ActivityKey, Range & { value: number | null }>;
  pending: PendingCalibration[];
}

export type ActivityKey = 'run_kcal_discount' | 'wrestling_kcal_per_session' | 'lifting_kcal_per_session';

export interface PendingCalibration {
  id: string;
  new_values: Partial<Record<ActivityKey, number>>;
  created_at: string;
  change: string;
}

/** POST setup/activity */
export interface ActivityResult {
  proposal: PendingCalibration & { referenced: boolean };
  section: ActivityView;
}

export interface Range {
  min: number;
  max: number;
  min_exclusive?: boolean;
}
