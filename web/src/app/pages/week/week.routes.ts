import { Routes } from '@angular/router';

/** The Week tab (?week=YYYY-Www, default the week in progress) and its detail views. */
export const WEEK_ROUTES: Routes = [
  { path: '', title: 'Check-in · Coach', loadComponent: () => import('./week-page').then((m) => m.WeekPage) },
];
