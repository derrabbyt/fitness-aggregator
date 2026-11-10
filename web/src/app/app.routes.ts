import { Routes } from '@angular/router';

/**
 * One lazily loaded route file per tab; a tab's detail views go in its own
 * `pages/<tab>/<tab>.routes.ts`, so tickets add routes without touching this file.
 */
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'home' },
  { path: 'home', loadChildren: () => import('./pages/home/home.routes').then((m) => m.HOME_ROUTES) },
  { path: 'week', loadChildren: () => import('./pages/week/week.routes').then((m) => m.WEEK_ROUTES) },
  { path: 'training', loadChildren: () => import('./pages/training/training.routes').then((m) => m.TRAINING_ROUTES) },
  { path: 'setup', loadChildren: () => import('./pages/setup/setup.routes').then((m) => m.SETUP_ROUTES) },
  // The old day view: by URL only, never linked.
  { path: 'legacy', title: 'Fitness Today', loadComponent: () => import('./legacy/legacy-day').then((m) => m.LegacyDay) },
  { path: '**', redirectTo: 'home' },
];
