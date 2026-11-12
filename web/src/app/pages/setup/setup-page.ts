import { ChangeDetectionStrategy, Component, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Icon } from '../../ui/icon';
import { State } from '../../ui/state';
import { SETUP_SECTIONS } from './setup-sections';
import { SectionSummary, SetupView } from './setup.types';

/**
 * Setup: the coach's setup as a list of sections, each with a one-line
 * summary, opening to view and edit (same rules as chat). Sections the coach
 * doesn't serve yet are listed as coming soon.
 */
@Component({
  selector: 'app-setup-page',
  imports: [PageHeader, RouterLink, Icon, State],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './setup-forms.css',
  template: `
    <div class="page">
      <app-page-header title="Setup" />
      @if (setup.data(); as s) {
        <div class="stack">
          @if (s.setup_open) {
            <p class="info small" role="status">Phase setup open in Telegram. Finish it there to edit here.</p>
          } @else if (!s.phase_active) {
            <p class="info small" role="status">No active phase. Start one in Telegram.</p>
          }
          <nav class="list" aria-label="Setup sections">
            @for (r of rows(); track r.key) {
              @if (r.summary) {
                <a class="row" [routerLink]="r.path">
                  <span class="txt">
                    <span class="m">{{ r.title }}</span>
                    <span class="t2 small sum">{{ r.summary }}</span>
                  </span>
                  <app-icon name="right" class="chev" />
                </a>
              } @else {
                <div class="row soon" aria-disabled="true">
                  <span class="txt">
                    <span class="m">{{ r.title }}</span>
                    <span class="t2 small sum">Coming soon</span>
                  </span>
                </div>
              }
            }
          </nav>
        </div>
      } @else if (setup.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="setup.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .list { background: var(--container); border-radius: var(--radius); box-shadow: var(--ring); overflow: hidden; }
    .row { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-top: 1px solid var(--divider);
      min-height: 64px; }
    .row:first-child { border-top: 0; }
    a.row { cursor: pointer; }
    @media (hover: hover) { a.row:hover { background: var(--inset); } }
    .soon .m { color: var(--text-2); }
    .txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
    .chev { --icon: 16px; color: var(--text-3); }
    @media (min-width: 900px) { .list, .stack { max-width: 640px; } }
  `,
})
export class SetupPage {
  protected readonly setup = viewResource<SetupView>('setup');

  protected readonly rows = computed(() => {
    const s = this.setup.data();
    return SETUP_SECTIONS.map((section) => ({
      ...section,
      summary: (s?.[section.key] as SectionSummary | undefined)?.summary ?? null,
    }));
  });

  constructor() {
    this.setup.load();
  }
}
