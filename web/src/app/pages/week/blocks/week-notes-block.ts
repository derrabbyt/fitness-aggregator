import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Card } from '../../../ui/card';
import { dayLabel } from '../../../ui/format';
import { WeekNotes, WeekView } from '../week.types';

const KIND: Record<'waist' | 'photos', string> = { waist: 'Waist', photos: 'Photos' };

/**
 * Week's notes and flags: the check-in's flags (a dot coloured by severity:
 * red needs action, amber to watch, gray for information), the context notes
 * of the week, the observations held back for the report, and the
 * measurements due the week after. Empty groups are left out.
 */
@Component({
  selector: 'app-week-notes-block',
  imports: [Card],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (notes(); as n) {
      <app-card label="Notes and flags">
        <div class="body">
        @if (empty()) {
          <p class="none t2">{{ n.flags ? 'No flags and no notes.' : 'No notes yet.' }}</p>
        }
        @if (n.flags?.length) {
          <ul class="list">
            @for (f of n.flags; track $index) {
              <li><i class="dot" [class]="f.severity"></i><span>{{ f.detail }}</span></li>
            }
          </ul>
        }
        @if (n.context_notes.length) {
          <div class="group">
            <div class="sub label">Context</div>
            <ul class="list">
              @for (c of n.context_notes; track c.id) {
                <li class="stacked"><span class="when t2 small num">{{ span(c.applies_from, c.applies_to) }}</span><span>{{ c.text }}</span></li>
              }
            </ul>
          </div>
        }
        @if (n.deferred.length) {
          <div class="group">
            <div class="sub label">Held for the report</div>
            <ul class="list">
              @for (d of n.deferred; track $index) {
                <li class="stacked"><span class="when t2 small num">{{ day(d.date) }}</span><span>{{ d.text }}</span></li>
              }
            </ul>
          </div>
        }
        @if (n.due_next_week.length) {
          <div class="group">
            <div class="sub label">Due next week</div>
            <ul class="list">
              @for (d of n.due_next_week; track $index) {
                <li><span>{{ kind[d.kind] }}</span><span class="t2 num">{{ day(d.date) }}</span></li>
              }
            </ul>
          </div>
        }
        </div>
      </app-card>
    }
  `,
  styles: `
    .none { margin: 0; }
    .list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
    .list li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: baseline; overflow-wrap: anywhere; }
    .body { display: grid; gap: 16px; }
    .sub { margin-bottom: 8px; }
    .list li.stacked { display: flex; flex-direction: column; gap: 2px; }
    .when { white-space: nowrap; }
    .dot { width: 8px; height: 8px; border-radius: 99px; background: var(--fill-2); transform: translateY(-1px); }
    .dot.watch { background: var(--warning); }
    .dot.action { background: var(--destructive); }
  `,
})
export class WeekNotesBlock {
  readonly view = input.required<WeekView>();

  protected readonly kind = KIND;
  protected readonly notes = computed(() => this.view().notes ?? null);
  protected readonly empty = computed(() => {
    const n: WeekNotes | null = this.notes();
    return !!n && !n.flags?.length && !n.context_notes.length && !n.deferred.length && !n.due_next_week.length;
  });
  protected readonly day = (d: string) => dayLabel(d);
  /** "Thu 19 Nov", "Mon 16 – Sun 22 Nov", "from Mon 16 Nov". */
  protected readonly span = (from: string, to: string | null) => {
    if (to == null) return `from ${dayLabel(from)}`;
    if (to === from) return dayLabel(from);
    return `${dayLabel(from)} – ${dayLabel(to)}`;
  };
}
