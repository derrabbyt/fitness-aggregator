/**
 * Weight read models (coach/coach-skills/schemas/web_home_weight*.schema.json).
 */

/** The weekly rate against the active phase's band, as the weekly check-in judges it. */
export type VsBand = 'in_band' | 'below_band' | 'above_band' | 'below_limit' | 'above_limit' | 'not_evaluated';

/** The latest weigh-in on or before the day (outliers are left out of the trend). */
export interface WeighIn {
  date: string;
  kg: number;
  outlier: boolean;
}

/** web_home_weight.schema.json: Home's `weight` part. */
export interface HomeWeight {
  weigh_in: WeighIn | null;
  weekly_rate_kg: number | null;
  vs_band: VsBand | null;
  /** The 7-day trend over the 14 days ending the day, oldest first. */
  series: { date: string; trend_kg: number | null }[];
}

export interface WeightBand {
  low: number;
  high: number;
  lower_limit: number | null;
  upper_limit: number | null;
}

export interface WeightDay {
  date: string;
  kg: number | null;
  outlier: boolean;
  trend_kg: number | null;
  band_low_kg: number | null;
  band_high_kg: number | null;
}

/** web_home_weight_detail.schema.json (GET /api/coach/home/weight?day=&weeks=1|2|4|12|26|all). */
export interface WeightDetail {
  date: string;
  weeks: 1 | 2 | 4 | 12 | 26 | 'all';
  weigh_in: WeighIn | null;
  trend_kg: number | null;
  weekly_rate_kg: number | null;
  vs_band: VsBand | null;
  band: WeightBand | null;
  series: WeightDay[];
  /** Every weigh-in up to the day, newest first. */
  recent: WeighIn[];
  waist: { date: string; cm: number }[];
  prediction: {
    start: string;
    end: string;
    predicted_kg: number;
    actual_kg: number | null;
    difference_kg: number | null;
    complete: boolean;
  } | null;
}
