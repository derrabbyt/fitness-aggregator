/** The lift detail's read model (coach/coach-skills/schemas/web_lift.schema.json). */
import { Freshness } from '../../api/types';
import { LiftStatus, TopSet } from './training.types';

export interface LiftChartPoint extends TopSet {
  date: string;
  session_id: string;
  /** Beat the best session since the baseline (never while paused). */
  pr: boolean;
  /** This session starts a new history after a baseline reset. */
  baseline_reset: boolean;
}

export interface LiftReset {
  from_date: string;
  reason: string | null;
  /** The session that started the new baseline; null until the lift is next trained. */
  session_date: string | null;
}

export type SessionStatus = 'progressing' | 'same' | 'declining' | 'stall' | 'new_baseline' | 'not_judged';

export interface LiftSession {
  date: string;
  session_id: string;
  top_set: TopSet | null;
  status: SessionStatus;
  not_judged_reason: 'after_break' | 'building_baseline' | 'no_working_sets' | 'other_location' | null;
  pr: boolean;
}

export interface LiftSessions {
  items: LiftSession[];
  offset: number;
  total: number;
  /** Offset of the next page ("show more"); null on the last page. */
  next_offset: number | null;
}

/** web_lift.schema.json (GET /api/coach/lift?exercise_id=&day=&offset=&limit=). */
export interface LiftView {
  date: string;
  freshness: Freshness;
  exercise_id: string;
  name: string;
  status: LiftStatus;
  not_judged_reason: 'after_break' | 'building_baseline' | null;
  bodyweight_exercise: boolean;
  last_session_date: string | null;
  latest: TopSet | null;
  counts: boolean;
  paused: boolean;
  chart: LiftChartPoint[];
  resets: LiftReset[];
  sessions: LiftSessions;
  controls: {
    classification: 'counts' | 'excluded' | null;
    paused_reason: string | null;
    reset_reasons: string[];
  };
}
