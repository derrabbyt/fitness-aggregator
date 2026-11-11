import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icon } from '../../ui/icon';
import { HomeView } from './home.types';

/**
 * Home's banner (ticket 05): only on today, and only when something needs
 * the user. An open proposal links to the Week page (approved in Telegram);
 * a waiting question only says where it waits.
 */
@Component({
  selector: 'app-home-banner',
  imports: [RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (banner(); as b) {
      <div class="banners" role="status">
        @if (b.proposal; as p) {
          <a class="banner tap" routerLink="/week">
            <app-icon name="alert" />
            <span class="text"><span class="m">Proposal waiting:</span> {{ p.change }}.
              <span class="t2">Decide in Telegram.</span></span>
            <app-icon name="right" class="chev" />
          </a>
        }
        @if (b.questions) {
          <div class="banner">
            <app-icon name="alert" />
            <span class="text">{{ b.questions === 1 ? 'The coach has a question' : 'The coach has ' + b.questions + ' questions' }}
              for you <span class="t2">in Telegram.</span></span>
          </div>
        }
      </div>
    }
  `,
  styles: `
    .banners { display: grid; gap: 8px; margin-bottom: 12px; }
    .banner { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: var(--radius);
      background: var(--banner-bg); box-shadow: 0 0 0 1px var(--banner-ring); --icon: 18px; }
    .banner > app-icon:first-child { color: var(--info); }
    .text { flex: 1; min-width: 0; }
    .chev { --icon: 16px; color: var(--text-3); }
    .tap { cursor: pointer; }
    @media (min-width: 900px) { .banners { margin-bottom: 16px; } }
  `,
})
export class HomeBannerComponent {
  readonly view = input.required<HomeView>();
  protected readonly banner = computed(() => (this.view().is_today ? (this.view().banner ?? null) : null));
}
