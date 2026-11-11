/**
 * Read models of the Setup sections that hold records (ticket 12):
 * coach/coach-skills/schemas/web_setup_{exercises,context_notes,profile,measurements}.schema.json.
 */

/** web_setup_exercises.schema.json */
export interface ExercisesView {
  since: string;
  exercises: ExerciseRow[];
}

export interface ExerciseRow {
  exercise_id: string;
  title: string;
  counts: boolean;
  classified: boolean;
  paused: boolean;
  paused_reason: string | null;
  bodyweight: boolean;
  sessions: number;
  last_date: string;
}

/** web_setup_context_notes.schema.json */
export interface ContextNotesView {
  today: string;
  tag_options: string[];
  notes: ContextNote[];
}

/** context_note.schema.json */
export interface ContextNote {
  id: string;
  created_at: string;
  text: string;
  applies_from: string;
  applies_to: string | null;
  tags: string[];
  exercise_id: string | null;
  suggest_unusable: Unusable;
  follow_up_question: string | null;
}

export type Unusable = 'yes' | 'maybe' | 'no';

/** web_setup_profile.schema.json */
export interface ProfileView {
  entries: { key: string; value: string }[];
  max_key: number;
  max_value: number;
  max_entries: number;
}

/** web_setup_measurements.schema.json */
export interface MeasurementsView {
  today: string;
  waist: {
    start: WaistValue | null;
    values: WaistValue[];
    next_due: string | null;
    min: number;
    max: number;
  };
  photos: {
    enabled: boolean | null;
    next_due: string | null;
    sets: PhotoSet[];
  };
}

export interface WaistValue {
  date: string;
  cm: number;
}

export interface PhotoSet {
  date: string;
  photos: Photo[];
}

export interface Photo {
  number: number;
  /** Relative to /api/coach/ (served read-only as an image). */
  url: string;
  caption: string | null;
  received_at: string;
}
