import { Routes } from '@angular/router';

/** The Week tab and its detail views (a placeholder until its ticket builds the page). */
export const WEEK_ROUTES: Routes = [
  { path: '', title: 'Week · Coach', data: { title: 'Week' },
    loadComponent: () => import('../../shell/placeholder-page').then((m) => m.PlaceholderPage) },
];
