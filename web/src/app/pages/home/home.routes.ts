import { Routes } from '@angular/router';

/** Home and its detail views (/home/<block>?day=…). Add a block's detail route here. */
export const HOME_ROUTES: Routes = [
  { path: '', title: 'Coach', loadComponent: () => import('./home-page').then((m) => m.HomePage) },
  { path: 'food', title: 'Food · Coach', loadComponent: () => import('./food-detail-page').then((m) => m.FoodDetailPage) },
  { path: 'steps', title: 'Steps · Coach', loadComponent: () => import('./steps-detail-page').then((m) => m.StepsDetailPage) },
  { path: 'sleep', title: 'Sleep · Coach', loadComponent: () => import('./sleep-detail-page').then((m) => m.SleepDetailPage) },
];
