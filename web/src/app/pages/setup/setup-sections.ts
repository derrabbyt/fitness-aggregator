/**
 * The Setup sections in the order the list shows them. `key` is the section's
 * part in the coach's `setup` view (its one-line summary); `path` its detail
 * route under /setup (setup.routes.ts). A section shows as "coming soon"
 * until the coach sends its part, so a ticket adds a section by adding the
 * coach part, the page and its route.
 */
export const SETUP_SECTIONS: readonly { key: string; title: string; path: string }[] = [
  { key: 'phase_targets', title: 'Phase & targets', path: 'phase' },
  { key: 'activity', title: 'Activity values', path: 'activity' },
  { key: 'messaging', title: 'Messaging', path: 'messaging' },
  { key: 'training_plan', title: 'Training plan', path: 'training-plan' },
  { key: 'exercises', title: 'Exercises', path: 'exercises' },
  { key: 'context_notes', title: 'Context notes', path: 'notes' },
  { key: 'profile', title: 'Profile', path: 'profile' },
  { key: 'measurements', title: 'Measurements', path: 'measurements' },
];
