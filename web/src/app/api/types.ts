/**
 * Types shared by several read models (coach/coach-skills/schemas/web_*.schema.json).
 * Page-specific types live next to their page (e.g. pages/home/home.types.ts).
 */

/** web_freshness.schema.json: how current the synced data is, now. */
export interface Freshness {
  last_sync_at: string | null;
  age_hours: number | null;
  stale: boolean;
}
