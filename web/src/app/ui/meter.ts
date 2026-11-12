import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Tone } from './tone';

/**
 * A thin progress bar: rounded track, fill clamped to 0-100 %.
 * `tone`: neutral (dark fill), muted (gray), ok / bad / warn (verdict colours).
 *
 *   <app-meter [value]="eaten" [max]="target" tone="bad" size="thin" />
 */
@Component({
  selector: 'app-meter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    role: 'progressbar',
    '[attr.aria-valuenow]': 'value() ?? 0',
    '[attr.aria-valuemax]': 'max() ?? 0',
    '[attr.aria-valuemin]': '0',
    '[attr.aria-label]': 'label() || null',
    '[class.thin]': "size() === 'thin'",
  },
  template: `<i [class]="tone()" [style.width.%]="percent()"></i>`,
  styles: `
    :host { display: block; height: 6px; background: var(--track); border-radius: 99px; overflow: hidden; }
    :host(.thin) { height: 4px; }
    i { display: block; height: 100%; border-radius: 99px; background: var(--fill); transition: width .5s ease; }
    i.muted { background: var(--fill-2); }
    i.ok { background: var(--success); }
    i.bad { background: var(--destructive); }
    i.warn { background: var(--warning); }
  `,
})
export class Meter {
  readonly value = input<number | null>(null);
  readonly max = input<number | null>(null);
  readonly tone = input<Tone>('neutral');
  readonly size = input<'regular' | 'thin'>('regular');
  readonly label = input('');

  protected readonly percent = computed(() => {
    const v = this.value(), m = this.max();
    if (v == null || !m || m <= 0) return 0;
    return Math.max(0, Math.min(100, (v / m) * 100));
  });
}
