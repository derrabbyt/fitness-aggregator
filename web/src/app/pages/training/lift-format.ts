/** Words and numbers for lifts, shared by the Training list and the lift detail. */
import { fmt } from '../../ui/format';
import { Tone } from '../../ui/tone';
import { LiftStatus, TopSet } from './training.types';
import { SessionStatus } from './lift.types';

/** Status words; colour only for progressing / declining / stall. */
export const LIFT_STATUS: Record<LiftStatus | SessionStatus, { text: string; tone: Tone }> = {
  progressing: { text: 'Progressing', tone: 'ok' },
  same: { text: 'Same', tone: 'muted' },
  declining: { text: 'Declining', tone: 'bad' },
  stall: { text: 'Stall', tone: 'warn' },
  paused: { text: 'Paused', tone: 'muted' },
  new_baseline: { text: 'New baseline', tone: 'muted' },
  not_judged: { text: 'Building', tone: 'muted' },
  not_recent: { text: 'Not recent', tone: 'muted' },
};

/** Why a session wasn't judged, in a few words. */
export const NOT_JUDGED: Record<string, string> = {
  after_break: 'Back after a break',
  building_baseline: 'Building',
  no_working_sets: 'No set in the rep range',
  other_location: 'Other gym',
};

/** Baseline reset reasons (mark_baseline_reset). */
export const RESET_REASONS: Record<string, string> = {
  technique_change: 'Technique change',
  rom_change: 'Range of motion change',
  exercise_swap: 'Exercise swap',
  other: 'Other',
};

/** 100 → "100", 102.5 → "102.5". */
export function kg(n: number): string {
  return fmt(n, Number.isInteger(n) ? 0 : 1);
}

/** "100 kg × 9"; bodyweight lifts show the effective load ("90 kg × 8 · +10 kg"). */
export function setText(s: TopSet | null, bodyweight: boolean): string {
  if (!s) return '–';
  if (bodyweight) {
    const extra = s.load_kg ? `+${kg(s.load_kg)} kg` : 'bodyweight';
    return `${kg(s.effective_load_kg)} kg × ${s.reps} · ${extra}`;
  }
  return `${kg(s.load_kg)} kg × ${s.reps}`;
}
