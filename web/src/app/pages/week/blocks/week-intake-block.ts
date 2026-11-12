import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { fmt, signed, weekday } from '../../../ui/format';
import { Meter } from '../../../ui/meter';
import { Favorable, Tone, targetTone } from '../../../ui/tone';
import { WeekView } from '../week.types';

const MACROS: { key: 'protein' | 'carbs' | 'fat' | 'fiber'; label: string; favorable: Favorable }[] = [
  { key: 'protein', label: 'Protein', favorable: 'up' },
  { key: 'carbs', label: 'Carbs', favorable: 'none' },
  { key: 'fat', label: 'Fat', favorable: 'down' },
  { key: 'fiber', label: 'Fiber', favorable: 'up' },
];

/**
 * Week's intake: the average eaten a day against the average target big,
 * the adherence result beside it (green when the week counted, red when it
 * didn't, plain while the week isn't judged), each day eaten against its
 * target on a thin bar (a partly logged day is marked and doesn't count),
 * then the macros a day against their targets, as on Home.
 */
@Component({
  selector: 'app-week-intake-block',
  imports: [Card, Meter],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (intake(); as i) {
      <app-card label="Intake">
        <div class="top">
          <div>
            <div>
              <span class="big num">{{ fmt(i.average.eaten_kcal) }}</span>
              @if (i.average.target_kcal != null) { <span class="t2 num"> / {{ fmt(i.average.target_kcal) }}</span> }
            </div>
            <div class="t2 small">kcal a day</div>
          </div>
          <div class="right">
            <div class="verdict num m" [class]="verdictTone()">{{ verdictValue() }}</div>
            <div class="t2 small">{{ verdictText() }}</div>
          </div>
        </div>

        <ul class="days">
          @for (d of i.days; track d.date) {
            <li>
              <span class="d small t2">{{ weekday(d.date) }}</span>
              @if (d.logged === 'missing') {
                <span class="track"></span>
                <span class="v small t2 num">– / {{ fmt(d.target_kcal) }}</span>
              } @else {
                <app-meter size="thin" [value]="d.eaten_kcal" [max]="d.target_kcal" tone="muted"
                           [label]="weekday(d.date) + ' eaten of target'" />
                <span class="v small num">
                  @if (d.logged === 'partial') { <span class="t2 partial">partly · </span> }
                  <span [class.t2]="d.logged === 'partial'">{{ fmt(d.eaten_kcal) }}</span><span class="t2"> / {{ fmt(d.target_kcal) }}</span>
                </span>
              }
            </li>
          }
        </ul>

        <div class="macros">
          @for (m of macros(); track m.key) {
            <div class="macro">
              <div class="label">{{ m.label }}</div>
              <div class="mv num">
                <span class="m" [class.bad]="m.tone === 'bad'">{{ fmt(m.eaten) }}</span>
                @if (m.target != null) { <span class="of"> / {{ fmt(m.target) }} g</span> } @else { <span class="of"> g</span> }
              </div>
              @if (m.target != null) {
                <app-meter size="thin" [value]="m.eaten" [max]="m.target" [tone]="m.tone" [label]="m.label + ' a day'" />
              }
            </div>
          }
        </div>
      </app-card>
    }
  `,
  styles: `
    .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .right { text-align: right; }
    .verdict { font-size: 15px; white-space: nowrap; }
    .verdict:not(.ok):not(.bad):not(.warn) { color: var(--text-2); }
    .days { list-style: none; margin: 16px 0 0; padding: 0; display: grid; gap: 8px; }
    .days li { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: 10px; }
    .track { display: block; height: 4px; border-radius: 99px; background: var(--track); }
    .v { min-width: 104px; text-align: right; white-space: nowrap; }
    .partial { font-style: normal; }
    .macros { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
    .mv { margin: 2px 0 6px; font-size: 14px; white-space: nowrap; }
    .of { font-weight: 400; color: var(--text-2); font-size: 12px; }
  `,
})
export class WeekIntakeBlock {
  readonly view = input.required<WeekView>();

  protected readonly fmt = fmt;
  protected readonly weekday = weekday;
  protected readonly intake = computed(() => this.view().intake ?? null);

  protected readonly verdictTone = computed<string>(() => {
    const r = this.intake()?.adherence.result;
    return r === 'pass' ? 'ok' : r === 'fail' ? 'bad' : '';
  });
  /** The deviation from target, or the days logged when it can't be told. */
  protected readonly verdictValue = computed(() => {
    const a = this.intake()?.adherence;
    if (!a) return '';
    if (a.deviation_pct != null) return `${signed(a.deviation_pct, 1)} %`;
    return `${a.days_logged} of ${a.days} logged`;
  });
  protected readonly verdictText = computed(() => {
    const a = this.intake()?.adherence;
    if (!a) return '';
    if (a.result === 'pass') return `counted · within ±${a.tolerance_pct} %`;
    if (a.result === 'fail') return a.deviation_pct != null ? `didn't count · ±${a.tolerance_pct} % counts` : `didn't count`;
    return a.deviation_pct != null ? `so far · ±${a.tolerance_pct} % counts` : 'so far';
  });
  protected readonly macros = computed(() => {
    const i = this.intake();
    if (!i) return [];
    return MACROS.map((m) => {
      const v = i.macros[m.key];
      const tone: Tone = targetTone(v.eaten_g, v.target_g, m.favorable);
      return { ...m, eaten: v.eaten_g, target: v.target_g, tone };
    });
  });
}
