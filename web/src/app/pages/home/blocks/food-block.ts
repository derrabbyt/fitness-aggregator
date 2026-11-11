import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { fmt, signed } from '../../../ui/format';
import { Meter } from '../../../ui/meter';
import { Favorable, targetTone } from '../../../ui/tone';
import { HomeView } from '../home.types';

const MACROS: { key: 'protein' | 'carbs' | 'fat' | 'fiber'; label: string; favorable: Favorable }[] = [
  { key: 'protein', label: 'Protein', favorable: 'up' },
  { key: 'carbs', label: 'Carbs', favorable: 'none' },
  { key: 'fat', label: 'Fat', favorable: 'down' },
  { key: 'fiber', label: 'Fiber', favorable: 'up' },
];

/**
 * Home's food block (the "bar" variant from ticket 01): kcal left big, eaten /
 * target beside it, one bar (ticket 14: above them a small line with how the
 * target is built, the parts that aren't 0), then protein / carbs / fat / fiber as four
 * compact columns with thin bars. Before a phase: what was eaten, no targets.
 */
@Component({
  selector: 'app-food-block',
  imports: [Card, Meter],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (food(); as f) {
      <app-card label="Food" link="/home/food" [queryParams]="dayQuery()">
        @if (math(); as parts) {
          <div class="math small t2 num">@for (part of parts; track $index) {@if ($index) { · }<span class="part">{{ part }}</span>}<span class="part"> = {{ fmt(f.build_up?.total_kcal) }}</span></div>
        }
        @if (f.kcal.target != null) {
          <div class="top">
            <div>
              <div class="big num" [class.bad]="over()">{{ fmt(abs(f.kcal.left)) }}</div>
              <div class="t2">{{ over() ? 'kcal over' : 'kcal left' }}</div>
            </div>
            <div class="right">
              <div class="mid num">{{ fmt(f.kcal.eaten ?? 0) }}<span class="of"> / {{ fmt(f.kcal.target) }}</span></div>
              @if (f.logged === 'partial') { <div class="t2">partly logged</div> }
            </div>
          </div>
          <app-meter [value]="f.kcal.eaten" [max]="f.kcal.target" [tone]="over() ? 'bad' : 'neutral'" label="Eaten of target" />
        } @else {
          <div class="eaten-only"><span class="big num">{{ fmt(f.kcal.eaten) }}</span><span class="t2">kcal eaten</span></div>
        }
        <div class="macros">
          @for (m of macros(); track m.key) {
            <div class="macro">
              <div class="label">{{ m.label }}</div>
              <div class="v num">
                <span class="m" [class.bad]="m.tone === 'bad'">{{ fmt(m.eaten) }}</span>
                @if (m.target != null) { <span class="of"> / {{ fmt(m.target) }} g</span> } @else { <span class="of"> g</span> }
              </div>
              @if (m.target != null) {
                <app-meter size="thin" [value]="m.eaten" [max]="m.target" [tone]="m.tone" [label]="m.label" />
              }
            </div>
          }
        </div>
      </app-card>
    }
  `,
  styles: `
    .math { margin: -2px 0 12px; line-height: 1.5; }
    .part { white-space: nowrap; }
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
    .right { text-align: right; }
    .eaten-only { display: flex; align-items: baseline; gap: 6px; }
    .of { font-weight: 400; color: var(--text-2); font-size: 12px; }
    .mid .of { font-size: inherit; }
    .macros { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
    .v { margin: 2px 0 6px; font-size: 14px; white-space: nowrap; }
  `,
})
export class FoodBlock {
  readonly view = input.required<HomeView>();
  readonly dayQuery = input<Record<string, string | null>>({});

  protected readonly fmt = fmt;
  protected readonly abs = (n: number | null) => (n == null ? null : Math.abs(n));
  protected readonly food = computed(() => this.view().food ?? null);
  /** "base 2,050 · steps −95 · workouts +300 · …" (the parts that aren't 0), null before a phase. */
  protected readonly math = computed(() => {
    const b = this.food()?.build_up;
    if (!b) return null;
    const parts = [`base ${fmt(b.base_kcal)}`];
    const add = (label: string, n: number) => n && parts.push(`${label} ${signed(n)}`);
    add('steps', b.steps_kcal);
    add('workouts', b.workouts_kcal);
    add('activities', b.activities_kcal);
    add('surplus', b.surplus_kcal);
    return parts;
  });
  protected readonly over = computed(() => (this.food()?.kcal.left ?? 0) < 0);
  protected readonly macros = computed(() => {
    const f = this.food();
    if (!f) return [];
    return MACROS.map((m) => {
      const v = f.macros[m.key];
      return { ...m, eaten: v.eaten_g, target: v.target_g, tone: targetTone(v.eaten_g, v.target_g, m.favorable) };
    });
  });
}
