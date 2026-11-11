import { signed } from '../../ui/format';
import { Tone } from '../../ui/tone';
import { VsBand } from './weight.types';

/**
 * The weekly rate's verdict colour: green in the band, amber just outside it,
 * red past a phase limit. Not judged (glycogen window, no phase, no band): no colour.
 * Symmetric on purpose, so it holds for a bulk and a cut alike.
 */
export function rateTone(vs: VsBand | null): Tone {
  switch (vs) {
    case 'in_band': return 'ok';
    case 'below_band': case 'above_band': return 'warn';
    case 'below_limit': case 'above_limit': return 'bad';
    default: return 'muted';
  }
}

/** The text class of a tone ('' when uncoloured). */
export function toneClass(tone: Tone): string {
  return tone === 'ok' || tone === 'bad' || tone === 'warn' ? tone : '';
}

/** 0.2 → "+0.20 kg/wk". */
export function rateText(rate: number | null): string {
  return rate == null ? '–' : `${signed(rate, 2)} kg/wk`;
}
