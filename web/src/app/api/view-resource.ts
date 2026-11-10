import { DestroyRef, inject, signal } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import { CoachApi, ViewQuery, errorMessage } from './coach-api';

/**
 * One read model on a page, as signals: `data`, `error`, `loading`,
 * `refreshing`, `refreshError`. Create it in a component's field initializer.
 *
 *   readonly home = viewResource<HomeView>('home');
 *   effect(() => { const day = this.day(); untracked(() => this.home.load({ day })); });  // (re)load per day
 *   this.home.refresh();                                  // sync, then reload (keeps the data shown)
 */
export class ViewResource<T> {
  private readonly api = inject(CoachApi);
  readonly data = signal<T | null>(null);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);
  readonly refreshing = signal(false);
  readonly refreshError = signal<string | null>(null);
  private query: ViewQuery = {};
  private sub?: Subscription;

  constructor(readonly name: string) {
    inject(DestroyRef).onDestroy(() => this.sub?.unsubscribe());
  }

  /** Load the view for `query`; the previous data stays until the answer arrives only if the query is the same. */
  load(query: ViewQuery = this.query): void {
    const same = JSON.stringify(query) === JSON.stringify(this.query) && this.data() != null;
    this.query = query;
    if (!same) this.data.set(null);
    this.loading.set(true);
    this.error.set(null);
    this.run(this.api.view<T>(this.name, query), false);
  }

  /** Sync MFP and Hevy in the coach, then show the fresh view. */
  refresh(): void {
    if (this.refreshing()) return;
    this.refreshing.set(true);
    this.refreshError.set(null);
    this.run(this.api.refresh<T>(this.name, this.query), true);
  }

  private run(request: Observable<T>, isRefresh: boolean): void {
    this.sub?.unsubscribe();
    this.sub = request.subscribe({
      next: (value) => {
        this.data.set(value);
        this.error.set(null);
        this.loading.set(false);
        this.refreshing.set(false);
      },
      error: (err: unknown) => {
        if (isRefresh) this.refreshError.set(errorMessage(err));
        else this.error.set(errorMessage(err));
        this.loading.set(false);
        this.refreshing.set(false);
      },
    });
  }
}

/** A ViewResource for the read model `name` (call in an injection context). */
export function viewResource<T>(name: string): ViewResource<T> {
  return new ViewResource<T>(name);
}
