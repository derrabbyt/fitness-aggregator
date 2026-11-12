import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel, fmt, signed } from '../../ui/format';
import { State } from '../../ui/state';
import { EditRow, EditState } from './edit-row';
import { PhaseTargetsView } from './setup.types';

/**
 * Setup › Phase & targets: the active phase, the targets in force today and
 * the step goal, the one value edited here. Targets change only through
 * proposals approved in Telegram; a phase starts there too.
 */
@Component({
  selector: 'app-phase-targets-page',
  imports: [PageHeader, Card, State, EditRow],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <div class="page">
      <app-page-header title="Phase & targets" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          <app-card label="Phase">
            @if (v.phase; as p) {
              <div class="mid">{{ p.name }}</div>
              <div class="t2 small">
                @if (p.week != null) { Week {{ p.week }} · since {{ day(p.start_date) }} }
                @else { Starts {{ day(p.start_date) }} }
              </div>
            } @else {
              <div class="mid">No active phase</div>
              <div class="t2 small">Start one in Telegram.</div>
            }
          </app-card>

          @if (v.targets; as t) {
            <app-card label="Today’s target">
              @if (t.today; as today) {
                <div><span class="big num">{{ fmt(today.kcal) }}</span><span class="t2"> kcal</span></div>
                <div class="t2 small num">Protein {{ today.protein_g }} g · carbs {{ today.carbs_g }} g · fat {{ today.fat_g }} g</div>
              } @else {
                <div class="t2">From the phase start.</div>
              }
            </app-card>

            <app-card label="Targets">
              <div class="kv"><span class="k">Average daily target</span><span class="v num">{{ fmt(t.avg_daily_target_kcal) }} kcal</span></div>
              <div class="kv"><span class="k">MyFitnessPal goal</span><span class="v num">{{ fmt(t.mfp_goal_kcal) }} kcal</span></div>
              <div class="kv">
                <span class="k">Base maintenance @if (t.avg_day_steps != null) { <span class="t2">at {{ fmt(t.avg_day_steps) }} steps</span> }</span>
                <span class="v num">{{ fmt(t.base_maintenance_kcal) }} kcal</span>
              </div>
              <div class="kv"><span class="k">Base at your step goal</span><span class="v num">{{ fmt(t.base_at_step_goal_kcal) }} kcal</span></div>
              <div class="kv"><span class="k">{{ t.surplus_kcal < 0 ? 'Deficit' : 'Surplus' }}</span><span class="v num">{{ signed(t.surplus_kcal) }} kcal</span></div>
            </app-card>

            <app-card label="Days at your step goal">
              <div class="kv"><span class="k">Rest day</span><span class="v num">{{ fmt(t.at_step_goal.rest) }} kcal</span></div>
              <div class="kv"><span class="k">Lifting day</span><span class="v num">{{ fmt(t.at_step_goal.lifting) }} kcal</span></div>
              <div class="kv"><span class="k">Wrestling day</span><span class="v num">{{ fmt(t.at_step_goal.wrestling) }} kcal</span></div>
            </app-card>
          }

          <app-card label="Steps">
            <app-edit-row label="Step goal" [value]="fmt(v.step_goal.value) + ' steps'" [editable]="v.step_goal.editable"
                          [editing]="edit.open() === 'step'" [busy]="edit.busy() === 'step'"
                          [error]="edit.errorFor('step')" [notice]="edit.noticeFor('step')"
                          (edit)="startStep(v.step_goal.value)" (cancel)="edit.cancel()" (save)="saveStep()">
              <input type="number" inputmode="numeric" step="500" [min]="v.step_goal.min" [max]="v.step_goal.max"
                     aria-label="Step goal" [value]="draft()" (input)="draft.set(value($event))" />
              <span class="unit">steps · default {{ fmt(v.step_goal.default) }}</span>
            </app-edit-row>
          </app-card>
        </div>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="3" />
      }
    </div>
  `,
  styles: `@media (min-width: 900px) { .stack { max-width: 640px; } }`,
})
export class PhaseTargetsPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<PhaseTargetsView>('setup/phase-targets');
  protected readonly edit = new EditState();
  protected readonly draft = signal('');
  protected readonly fmt = fmt;
  protected readonly signed = signed;
  protected readonly day = (d: string) => dayLabel(d);

  constructor() {
    this.view.load();
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  protected startStep(current: number): void {
    this.draft.set(String(current));
    this.edit.start('step');
  }

  protected saveStep(): void {
    const raw = this.draft().trim();
    const steps = raw === '' ? null : Number(raw);
    this.edit.save('step', this.api.command<PhaseTargetsView>('setup/step-goal', { step_goal: steps }), (v) => {
      this.view.data.set(v);
      return `Saved. Step goal ${fmt(v.step_goal.value)}.`;
    });
  }
}
