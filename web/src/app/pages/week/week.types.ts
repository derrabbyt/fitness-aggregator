/**
 * The Week read model (coach/coach-skills/schemas/web_week.schema.json).
 * The number blocks (ticket 07) are parts of `week` with their own schemas;
 * a block adds its optional key to WeekView and its type below.
 */
import { Freshness } from '../../api/types';

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
  freshness: Freshness;
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
  source: 'weekly_decision' | 'user_counter' | 'user_request' | 'phase_start';
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
