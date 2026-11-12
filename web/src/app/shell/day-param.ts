import { computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { isIsoDate, todayIso } from '../ui/format';

/**
 * The page's day, from `?day=YYYY-MM-DD` (absent = today, so today's URL stays
 * clean and a bookmark always opens today). Call in an injection context.
 *
 *   readonly day = injectDay();
 *   day.value()        // '2026-11-10'
 *   day.isToday()
 *   day.go('2026-11-08')
 *   day.query()        // { day: '2026-11-08' } or { day: null } for today (for links)
 */
export function injectDay() {
  const route = inject(ActivatedRoute);
  const router = inject(Router);
  const params = toSignal(route.queryParamMap, { initialValue: route.snapshot.queryParamMap });
  const today = todayIso();
  const value = computed(() => {
    const raw = params().get('day');
    return isIsoDate(raw) && raw < today ? raw : today;
  });
  return {
    today,
    value,
    isToday: computed(() => value() === today),
    query: computed(() => ({ day: value() === today ? null : value() })),
    go(day: string): void {
      if (!isIsoDate(day) || day > today) return;
      void router.navigate([], { relativeTo: route, queryParams: { day: day === today ? null : day },
        queryParamsHandling: 'merge', replaceUrl: true });
    },
  };
}
