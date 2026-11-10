import { Routes } from '@angular/router';

/** The Training tab and its detail views (a placeholder until its ticket builds the page). */
export const TRAINING_ROUTES: Routes = [
  { path: '', title: 'Training · Coach', data: { title: 'Training' },
    loadComponent: () => import('../../shell/placeholder-page').then((m) => m.PlaceholderPage) },
];
