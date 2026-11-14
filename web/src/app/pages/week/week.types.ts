/**
 * The Week read model (coach/coach-skills/schemas/web_week.schema.json).
 * The number blocks (ticket 07) are parts of `week` with their own schemas;
 * a block adds its optional key to WeekView and its type below.
 */
import { Freshness } from '../../api/types';
import { Balance } from '../../ui/format';
import { VsBand, WeightDay } from '../home/weight.types';

export type WeekState = 'in_progress' | 'decided' | 'awaiting' | 'failed' | 'none';
export type SkipReason = 'unusable' | 'glycogen_window' | 'adherence_gate' | 'sport_load';
export type ProposalStatus = 'open' | 'approved' | 'rejected' | 'superseded' | 'blocked_by_guardrail';

/** GET /api/coach/week?week=YYYY-Www (default: the week holding today). */
export interface WeekView {
  iso_week: string;
  start: string;
  end: string;
  is_current: boolean;
  state: WeekState;
  phase_week: number | null;
  prev_week: string | null;
  next_week: string | null;
  checkin_at: string | null;
  /** One line for a week without a decision (awaiting, failed, none). */
  note: string | null;
  decision: WeekDecision | null;
  so_far: { days: number; weigh_ins: number; food_days_logged: number } | null;
  proposals: Proposal[];
  report: string | null;
  /** Block, phase and photo reviews sent during the week, oldest first. */
  reviews: WeekReview[];
  freshness: Freshness;
  /** The number blocks (ticket 07); null when no phase was active during the week. */
  weight?: WeekWeight | null;
  intake?: WeekIntake | null;
  training?: WeekTraining | null;
  notes?: WeekNotes | null;
}

/** check_in: the numbers the week's check-in stored; so_far: the week not judged yet. */
export type WeekSource = 'check_in' | 'so_far';

/** web_week_weight.schema.json */
export interface WeekWeight {
  source: WeekSource;
  trend_kg: number | null;
  prev_trend_kg: number | null;
  weekly_rate_kg: number | null;
  /** week: the judged week's rate; last_7_days: the 7 days ending today (as on Home). */
  rate_window: 'week' | 'last_7_days';
  band: { low: number; high: number } | null;
  vs_band: VsBand | null;
  weigh_ins: number;
  weigh_ins_needed: number;
  days: number;
  /** The day before the week to its last day so far, the band corridor from that day's trend. */
  series: WeightDay[];
}

/** web_week_intake.schema.json */
export interface WeekIntake {
  source: WeekSource;
  /** balance_kcal: eaten minus the day's estimated burn (+ surplus, − deficit); null without food. */
  days: { date: string; eaten_kcal: number | null; target_kcal: number; logged: 'complete' | 'partial' | 'missing';
    balance_kcal: number | null }[];
  /** The complete days' balances added up, and as kg (a rough guide). */
  balance: Balance;
  average: { eaten_kcal: number | null; target_kcal: number | null; days: number };
  adherence: {
    result: 'pass' | 'fail' | 'not_judged';
    deviation_pct: number | null;
    tolerance_pct: number;
    days_logged: number;
    days: number;
  };
  macros: {
    protein: WeekMacro;
    carbs: WeekMacro;
    fat: WeekMacro;
    fiber: { eaten_g: number | null; target_g: number | null; target_max_g: number | null };
  };
}

export interface WeekMacro {
  eaten_g: number | null;
  target_g: number | null;
}

/** web_week_training.schema.json */
export interface WeekTraining {
  source: WeekSource;
  lifts: {
    progressing: number;
    counted: number;
    stalls: { exercise_id: string; name: string }[];
    prs: { exercise_id: string; name: string; date: string; e1rm_kg: number | null }[];
    deload_signal: boolean;
  } | null;
  sessions: { done: number; planned: number; skipped: number };
  steps: {
    goal: number;
    average: number | null;
    days_at_goal: number;
    days: { date: string; tracked: boolean; steps: number | null }[];
  };
}

/** web_week_notes.schema.json */
export interface WeekNotes {
  context_notes: { id: string; text: string; applies_from: string; applies_to: string | null; tags: string[] }[];
  /** The check-in's flags; null until the week is judged. */
  flags: { code: string; severity: 'info' | 'watch' | 'action'; detail: string }[] | null;
  deferred: { date: string; text: string }[];
  due_next_week: { date: string; kind: 'waist' | 'photos' }[];
}

/** A review as sent in Telegram, read-only. */
export interface WeekReview {
  id: number;
  kind: 'block' | 'phase' | 'photo';
  title: string;
  /** The days it looks back over. */
  period_start: string;
  period_end: string;
  text: string;
  sent_at: string;
}

export interface WeekDecision {
  outcome: 'hold' | 'change';
  change_kcal: number | null;
  direction: 'increase' | 'decrease' | 'hold';
  why: string;
  counts: boolean;
  skip: { reason: SkipReason; text: string } | null;
  confirmation: { weeks: number; required: number; met: boolean };
  decided_at: string;
}

/** A proposal, read-only: approve / reject / counter stay in Telegram. */
export interface Proposal {
  id: string;
  type: 'calorie_change' | 'calibration_change';
  source: 'weekly_decision' | 'user_counter' | 'user_request' | 'phase_start' | 'phase_review';
  status: ProposalStatus;
  based_on_week: string | null;
  change: string;
  delta_kcal: number | null;
  new_values: Record<string, number> | null;
  reason: string;
  agent_disagrees: string | null;
  user_reason: string | null;
  created_at: string;
  decided_at: string | null;
  guardrail: { passed: boolean; details: { violation: string; text: string; earliest_checkin: string | null }[] };
  applied_on: string | null;
  mfp_goal_after_kcal: number | null;
  avg_daily_target_kcal: { before: number; after: number } | null;
}
