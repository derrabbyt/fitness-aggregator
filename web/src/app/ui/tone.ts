/**
 * Verdict colours: colour only where something is on or off target, and only
 * in the direction that matters for the metric (docs/design/sure-reference.md §1, §6).
 */
export type Tone = 'neutral' | 'muted' | 'ok' | 'bad' | 'warn';

/** Which way is good for a metric: up (reach it: protein, fiber), down (stay under: fat), none. */
export type Favorable = 'up' | 'down' | 'none';

/** A macro bar's tone: ok once an "up" target is reached, bad over a "down" target, else muted. */
export function targetTone(value: number | null, target: number | null, favorable: Favorable): Tone {
  if (value == null || target == null) return 'muted';
  if (favorable === 'up' && value >= target) return 'ok';
  if (favorable === 'down' && value > target) return 'bad';
  return 'muted';
}

/** CSS colour of a tone, for SVG strokes and fills. */
export function toneColor(tone: Tone): string {
  switch (tone) {
    case 'ok': return 'var(--success)';
    case 'bad': return 'var(--destructive)';
    case 'warn': return 'var(--warning)';
    case 'neutral': return 'var(--fill)';
    default: return 'var(--fill-2)';
  }
}
