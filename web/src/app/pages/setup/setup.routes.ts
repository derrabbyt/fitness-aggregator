import { Routes } from '@angular/router';

/**
 * The Setup tab (the section list) and one route per section (/setup/<path>,
 * the paths in setup-sections.ts). A new section adds its route here.
 */
export const SETUP_ROUTES: Routes = [
  { path: '', title: 'Setup · Coach', loadComponent: () => import('./setup-page').then((m) => m.SetupPage) },
  { path: 'phase', title: 'Phase & targets · Coach',
    loadComponent: () => import('./phase-targets-page').then((m) => m.PhaseTargetsPage) },
  { path: 'activity', title: 'Activity values · Coach',
    loadComponent: () => import('./activity-page').then((m) => m.ActivityPage) },
  { path: 'messaging', title: 'Messaging · Coach',
    loadComponent: () => import('./messaging-page').then((m) => m.MessagingPage) },
  { path: 'training-plan', title: 'Training plan · Coach',
    loadComponent: () => import('./training-plan-page').then((m) => m.TrainingPlanPage) },
];
