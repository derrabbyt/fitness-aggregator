import { Component, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';

interface Nutrition {
  calories: number;
  goal_calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

interface MfpWorkout {
  name: string;
  source: string;
  minutes: number;
  distance_km: number | null;
  kcal: number;
}

interface HevySet {
  weight_kg?: number;
  reps?: number;
  distance_meters?: number;
  duration_seconds?: number;
}

interface HevyWorkout {
  name: string;
  start: string;
  minutes: number | null;
  exercises: { title: string; sets: HevySet[] }[];
}

interface Today {
  date: string;
  nutrition: Nutrition | null;
  steps: number | null;
  weight: { kg: number; date: string } | null;
  mfp_workouts: MfpWorkout[];
  hevy_workouts: HevyWorkout[];
  errors: Record<string, string>;
}

@Component({
  selector: 'app-root',
  imports: [DecimalPipe],
  template: `
    <h1>{{ date() === today ? 'Today' : 'Day' }} {{ date() }}</h1>
    <nav>
      <button (click)="shift(-1)" [disabled]="loading()" aria-label="Previous day">‹</button>
      <input type="date" [value]="date()" [max]="today" [disabled]="loading()" (change)="pick($event)" />
      <button (click)="shift(1)" [disabled]="loading() || date() >= today" aria-label="Next day">›</button>
      @if (date() !== today) {
        <button (click)="go(today)" [disabled]="loading()">Today</button>
      }
      <button (click)="load()" [disabled]="loading()">{{ loading() ? 'Loading…' : 'Refresh' }}</button>
    </nav>

    @if (error()) {
      <p class="error">Could not load: {{ error() }}</p>
    }

    @if (data(); as d) {
      @for (e of errorList(d); track e[0]) {
        <p class="error">{{ e[0] }}: {{ e[1] }}</p>
      }

      <h2>Nutrition</h2>
      @if (d.nutrition; as n) {
        <table>
          <tr><th>kcal</th><td>{{ n.calories | number: '1.0-0' }} / {{ n.goal_calories | number: '1.0-0' }}</td></tr>
          <tr><th>Protein</th><td>{{ n.protein | number: '1.0-0' }} g</td></tr>
          <tr><th>Carbs</th><td>{{ n.carbs | number: '1.0-0' }} g</td></tr>
          <tr><th>Fat</th><td>{{ n.fat | number: '1.0-0' }} g</td></tr>
        </table>
      } @else {
        <p>No data.</p>
      }

      <h2>Steps</h2>
      <p>{{ d.steps != null ? (d.steps | number) : 'No data' }}</p>

      <h2>Body weight</h2>
      @if (d.weight; as w) {
        <p>{{ w.kg | number: '1.1-1' }} kg{{ w.date !== d.date ? ' (last logged ' + w.date + ')' : '' }}</p>
      } @else {
        <p>No weigh-in in the last 90 days.</p>
      }

      <h2>Workouts (MyFitnessPal)</h2>
      @if (d.mfp_workouts.length) {
        <table>
          <tr><th>Workout</th><th>Source</th><th>Min</th><th>km</th><th>kcal</th></tr>
          @for (w of d.mfp_workouts; track $index) {
            <tr>
              <td>{{ w.name }}</td><td>{{ w.source }}</td><td>{{ w.minutes }}</td>
              <td>{{ w.distance_km != null ? (w.distance_km | number: '1.2-2') : '–' }}</td>
              <td>{{ w.kcal | number: '1.0-0' }}</td>
            </tr>
          }
        </table>
      } @else {
        <p>None.</p>
      }

      <h2>Workouts (Hevy)</h2>
      @for (w of d.hevy_workouts; track $index) {
        <h3>{{ w.name }} – {{ w.start.slice(11) }}{{ w.minutes != null ? ', ' + w.minutes + ' min' : '' }}</h3>
        <ul>
          @for (e of w.exercises; track $index) {
            <li>{{ e.title }}: {{ setsText(e.sets) }}</li>
          }
        </ul>
      } @empty {
        <p>None.</p>
      }
    }
  `,
  styles: [
    `
      :host { display: block; font-family: sans-serif; max-width: 720px; margin: 1rem auto; padding: 0 1rem; }
      table { border-collapse: collapse; }
      th, td { text-align: left; padding: 0.2rem 0.8rem 0.2rem 0; }
      .error { color: #b00020; }
      nav { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
    `,
  ],
})
export class App {
  private readonly http = inject(HttpClient);
  protected readonly data = signal<Today | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly today = isoDate(new Date());
  protected readonly date = signal(new URLSearchParams(location.search).get('date') ?? this.today);

  constructor() {
    this.load();
  }

  protected go(date: string): void {
    if (!date || date > this.today) return;
    this.date.set(date);
    history.replaceState(null, '', date === this.today ? location.pathname : `?date=${date}`);
    this.load();
  }

  protected shift(days: number): void {
    const d = new Date(this.date() + 'T12:00:00');
    d.setDate(d.getDate() + days);
    this.go(isoDate(d));
  }

  protected pick(event: Event): void {
    this.go((event.target as HTMLInputElement).value);
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.data.set(null);
    this.http.get<Today>('/api/day', { params: { date: this.date() } }).subscribe({
      next: (d) => {
        this.data.set(d);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e.message ?? String(e));
        this.loading.set(false);
      },
    });
  }

  protected errorList(d: Today): [string, string][] {
    return Object.entries(d.errors ?? {});
  }

  protected setsText(sets: HevySet[]): string {
    return sets
      .map((s) => {
        if (s.reps != null) return `${s.weight_kg ?? 0} kg × ${s.reps}`;
        if (s.distance_meters != null) return `${(s.distance_meters / 1000).toFixed(2)} km`;
        if (s.duration_seconds != null) {
          const m = Math.floor(s.duration_seconds / 60);
          return `${m}:${String(s.duration_seconds % 60).padStart(2, '0')} min`;
        }
        return '?';
      })
      .join(', ');
  }
}

/** YYYY-MM-DD in local time (toISOString would use UTC). */
function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
