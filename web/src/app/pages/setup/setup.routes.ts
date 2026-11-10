import { Routes } from '@angular/router';

/** The Setup tab and its detail views (a placeholder until its ticket builds the page). */
export const SETUP_ROUTES: Routes = [
  { path: '', title: 'Setup · Coach', data: { title: 'Setup' },
    loadComponent: () => import('../../shell/placeholder-page').then((m) => m.PlaceholderPage) },
];
