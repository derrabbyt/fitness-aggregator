import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

/**
 * An on/off switch (role="switch"), neutral like the rest of the UI. The
 * visible label sits next to it (a column header or the row's label); `label`
 * is what a screen reader hears. 44px hit area on touch.
 *
 *   <app-switch [on]="e.counts" [label]="'Counts for progression: ' + e.title" (toggle)="set(!e.counts)" />
 */
@Component({
  selector: 'app-switch',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" role="switch" class="switch" [attr.aria-checked]="on()" [attr.aria-label]="label()"
            [disabled]="disabled()" (click)="toggle.emit()">
      <span class="knob"></span>
    </button>
  `,
  styles: `
    :host { display: inline-flex; flex: none; }
    .switch { position: relative; width: 44px; height: 26px; border-radius: 13px; background: var(--track);
      transition: background-color .15s ease; }
    .switch[aria-checked="true"] { background: var(--fill); }
    .knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%;
      background: #fff; box-shadow: 0 1px 2px rgba(0, 0, 0, .2); transition: transform .15s ease; }
    .switch[aria-checked="true"] .knob { transform: translateX(18px); background: var(--container); }
    .switch[disabled] { opacity: .6; cursor: default; }
    .switch:focus-visible { outline: 2px solid var(--info); outline-offset: 2px; }
    @media (pointer: coarse) {
      .switch::after { content: ""; position: absolute; inset: -9px -4px; }
    }
  `,
})
export class Switch {
  readonly on = input(false);
  readonly label = input.required<string>();
  readonly disabled = input(false);
  readonly toggle = output<void>();
}
