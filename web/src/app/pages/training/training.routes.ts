import { Routes } from '@angular/router';

/** The Training tab and its detail views: /training/lift/<exercise_id>, always as of today (no ?day=). */
export const TRAINING_ROUTES: Routes = [
  { path: '', title: 'Training · Coach',
    loadComponent: () => import('./training-page').then((m) => m.TrainingPage) },
  { path: 'lift/:id', title: 'Lift · Coach',
    loadComponent: () => import('./lift-page').then((m) => m.LiftPage) },
];
