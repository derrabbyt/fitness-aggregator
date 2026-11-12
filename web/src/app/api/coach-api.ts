import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Query parameters of a read model, e.g. { day: '2026-11-10' }; null/empty values are left out. */
export type ViewQuery = Record<string, string | null | undefined>;

/**
 * The coach's HTTP API, which fa-api passes through under /api/coach/
 * (coach/src/fa_coach/web_adapter.py). Each read model has a JSON schema in
 * coach/coach-skills/schemas/web_*.schema.json; its TypeScript type sits next
 * to the page that shows it.
 *
 *   api.view<HomeView>('home', { day })           GET  /api/coach/home?day=…
 *   api.refresh<HomeView>('home', { day })        POST /api/coach/refresh/home?day=… (sync, then the view)
 *   api.command<T>('setup/step-goal', { value })  POST /api/coach/setup/step-goal
 */
@Injectable({ providedIn: 'root' })
export class CoachApi {
  private readonly http = inject(HttpClient);
  static readonly BASE = '/api/coach';

  view<T>(name: string, query: ViewQuery = {}): Observable<T> {
    return this.http.get<T>(`${CoachApi.BASE}/${name}`, { params: params(query) });
  }

  refresh<T>(name: string, query: ViewQuery = {}): Observable<T> {
    return this.http.post<T>(`${CoachApi.BASE}/refresh/${name}`, null, { params: params(query) });
  }

  command<T>(name: string, body: object = {}): Observable<T> {
    return this.http.post<T>(`${CoachApi.BASE}/${name}`, body);
  }
}

function params(query: ViewQuery): HttpParams {
  let p = new HttpParams();
  for (const [k, v] of Object.entries(query)) if (v != null && v !== '') p = p.set(k, v);
  return p;
}

/** The plain reason to show for a failed request: the coach's own `{error}` text when it sent one. */
export function errorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const body = err.error as { error?: unknown } | null;
    if (body && typeof body === 'object' && typeof body.error === 'string') return body.error;
    if (err.status === 0) return "The server isn't reachable.";
    if (err.status === 502 || err.status === 503 || err.status === 504) return "The coach isn't reachable right now.";
    return `${err.status} ${err.statusText || 'error'}`.trim();
  }
  return err instanceof Error ? err.message : String(err);
}
