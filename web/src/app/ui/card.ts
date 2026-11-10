import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Icon } from './icon';

/**
 * A card: white container, 12px radius, hairline ring. With `link` the whole
 * card is a link to its detail (chevron in the header).
 *
 *   <app-card label="Food" link="/home/food" [queryParams]="{ day }">…</app-card>
 */
@Component({
  selector: 'app-card',
  imports: [RouterLink, NgTemplateOutlet, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (link(); as to) {
      <a class="card tap" [routerLink]="to" [queryParams]="queryParams()">
        <ng-container *ngTemplateOutlet="body" />
      </a>
    } @else {
      <section class="card" [attr.aria-label]="label() || null">
        <ng-container *ngTemplateOutlet="body" />
      </section>
    }
    <ng-template #body>
      @if (label()) {
        <div class="head">
          <span class="label">{{ label() }}</span>
          @if (link()) { <app-icon name="right" class="chev" /> }
        </div>
      }
      <ng-content />
    </ng-template>
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .card {
      display: flex; flex-direction: column; width: 100%;
      background: var(--container); border-radius: var(--radius); box-shadow: var(--ring); padding: 16px;
    }
    .tap { cursor: pointer; transition: transform .12s ease; }
    .tap:active { transform: scale(.995); }
    @media (hover: hover) { .tap:hover { box-shadow: var(--ring), 0 2px 8px rgba(11, 11, 11, .04); } }
    .head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; min-height: 16px; }
    .chev { --icon: 16px; color: var(--text-3); }
    @media (min-width: 900px) { .card { padding: 20px; } }
  `,
})
export class Card {
  readonly label = input('');
  readonly link = input<string | null>(null);
  readonly queryParams = input<Record<string, string | null> | null>(null);
}
