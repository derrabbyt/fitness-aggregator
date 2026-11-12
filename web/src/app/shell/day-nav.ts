import { ChangeDetectionStrategy, Component, ElementRef, computed, input, output, viewChild } from '@angular/core';
import { addDays, dayLabel, parseIso, todayIso } from '../ui/format';
import { Icon } from '../ui/icon';
import { PageHeader } from './page-header';

/**
 * The page header for one day: previous / next arrows around "Today" or the
 * date, a date picker, and room for actions (e.g. the refresh control).
 *
 *   <app-day-nav [day]="day.value()" (dayChange)="day.go($event)">
 *     <app-refresh-button actions … />
 *   </app-day-nav>
 */
@Component({
  selector: 'app-day-nav',
  imports: [PageHeader, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-page-header [title]="title()" [sub]="sub()" [back]="back()" [backQuery]="backQuery()">
      @if (!back()) {
        <button prev type="button" class="iconbtn" aria-label="Previous day" (click)="shift(-1)">
          <app-icon name="left" />
        </button>
      }
      @if (!back()) {
        <button next type="button" class="iconbtn" aria-label="Next day" [disabled]="isToday()" (click)="shift(1)">
          <app-icon name="right" />
        </button>
      }
      <span actions class="picker">
        <button type="button" class="iconbtn" aria-label="Pick a date" (click)="openPicker()">
          <app-icon name="calendar" />
        </button>
        <input #picker type="date" tabindex="-1" aria-hidden="true" [max]="today" [value]="day()"
               (change)="pick($event)" />
      </span>
      <ng-content select="[actions]" ngProjectAs="[actions]" />
    </app-page-header>
  `,
  styles: `
    .picker { position: relative; display: inline-grid; }
    input { position: absolute; inset: 0; opacity: 0; pointer-events: none; width: 100%; height: 100%; border: 0; padding: 0; }
  `,
})
export class DayNav {
  readonly day = input.required<string>();
  /** Detail views: a back link replaces the day arrows (the date picker stays). */
  readonly back = input<string | null>(null);
  readonly backQuery = input<Record<string, string | null> | null>(null);
  /** Title override (e.g. "Food"); the date then moves to the sub line. */
  readonly heading = input('');
  readonly dayChange = output<string>();

  protected readonly today = todayIso();
  protected readonly isToday = computed(() => this.day() >= this.today);
  private readonly picker = viewChild.required<ElementRef<HTMLInputElement>>('picker');

  protected readonly title = computed(() =>
    this.heading() || (this.isToday() ? 'Today' : dayLabel(this.day())));
  protected readonly sub = computed(() => {
    const date = dayLabel(this.day());
    if (this.heading()) return this.isToday() ? `Today · ${date}` : date;
    if (this.isToday()) return date;
    const back = Math.round((parseIso(this.today).getTime() - parseIso(this.day()).getTime()) / 86_400_000);
    return back === 1 ? 'Yesterday' : `${back} days ago`;
  });

  protected shift(days: number): void {
    const next = addDays(this.day(), days);
    if (next <= this.today) this.dayChange.emit(next);
  }

  protected openPicker(): void {
    const el = this.picker().nativeElement;
    try {
      el.showPicker();
    } catch {
      el.focus();
      el.click();
    }
  }

  protected pick(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    if (value) this.dayChange.emit(value);
  }
}
