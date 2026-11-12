import { Routes } from '@angular/router';

/** The Training tab and its detail views (ticket 09 adds the lift detail here). */
export const TRAINING_ROUTES: Routes = [
  { path: '', title: 'Training · Coach',
    loadComponent: () => import('./training-page').then((m) => m.TrainingPage) },
];
