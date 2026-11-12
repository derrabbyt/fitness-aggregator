import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { CoachApi } from '../../api/coach-api';
import { viewResource } from '../../api/view-resource';
import { PageHeader } from '../../shell/page-header';
import { Card } from '../../ui/card';
import { dayLabel, fmt } from '../../ui/format';
import { State } from '../../ui/state';
import { EditRow, EditState } from './edit-row';
import { MeasurementsView, Photo, PhotoSet } from './setup-records.types';

/**
 * Setup › Measurements: waist values (the one from the phase start, then
 * each stored value; add one, chat's range check) and the progress photo
 * sets by date. Photos are only shown: the coach serves each one read-only
 * (`GET /api/coach/photos/<date>/<n>`); a tap opens it larger.
 */
@Component({
  selector: 'app-measurements-page',
  imports: [PageHeader, Card, State, EditRow],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./setup-forms.css', './setup-records.css'],
  template: `
    <div class="page">
      <app-page-header title="Measurements" back="/setup" />
      @if (view.data(); as v) {
        <div class="stack">
          <app-card label="Waist">
            <app-edit-row label="Latest" [hint]="waistDue(v)" [value]="latest(v)" [editable]="true"
                          editLabel="Add" saveLabel="Save"
                          [editing]="edit.open() === 'waist'" [busy]="edit.busy() === 'waist'"
                          [error]="edit.errorFor('waist')" [notice]="edit.noticeFor('waist')"
                          (edit)="startWaist(v)" (cancel)="edit.cancel()" (save)="saveWaist()">
              <input type="number" inputmode="decimal" step="0.1" [min]="v.waist.min" [max]="v.waist.max"
                     aria-label="Waist in cm" [value]="cm()" (input)="cm.set(value($event))" />
              <span class="unit">cm on</span>
              <input type="date" aria-label="Measured on" [max]="v.today" [value]="date()" (input)="date.set(value($event))" />
            </app-edit-row>
            @if (history(v).length) {
              <ul class="rows hist">
                @for (w of history(v); track $index) {
                  <li class="kv">
                    <span class="k">{{ day(w.date) }}@if (w.start) { <span class="t2"> · phase start</span> }</span>
                    <span class="v num">{{ cmText(w.cm) }}</span>
                  </li>
                }
              </ul>
            }
          </app-card>

          <app-card label="Progress photos">
            @if (photoLine(v); as line) { <p class="t2 small sub">{{ line }}</p> }
            @if (!v.photos.sets.length) {
              <p class="t2 small empty">No photos yet. Send them to the coach in Telegram.</p>
            }
            @for (s of v.photos.sets; track s.date) {
              <section class="set" [attr.aria-label]="'Photo set of ' + day(s.date)">
                <div class="set-head"><span class="m">{{ day(s.date) }}</span>
                  <span class="t2 small">{{ s.photos.length }} photo{{ s.photos.length === 1 ? '' : 's' }}</span></div>
                <div class="thumbs">
                  @for (p of s.photos; track p.number) {
                    <button type="button" class="thumb" (click)="open(s, p)" [attr.aria-label]="alt(s, p) + ', open larger'">
                      <img [src]="src(p)" [alt]="alt(s, p)" loading="lazy" decoding="async" referrerpolicy="no-referrer" />
                      @if (p.caption) { <span class="cap small">{{ p.caption }}</span> }
                    </button>
                  }
                </div>
              </section>
            }
          </app-card>
        </div>

        <dialog #viewer class="viewer" (close)="shown.set(null)" (click)="closeOnBackdrop($event)" aria-label="Photo">
          @if (shown(); as s) {
            <div class="frame">
              <img [src]="src(s.photo)" [alt]="alt(s.set, s.photo)" referrerpolicy="no-referrer" />
              <div class="bar">
                <button type="button" class="btn" (click)="step(-1)" [disabled]="!canStep(-1)" aria-label="Previous photo">‹</button>
                <span class="small grow">{{ day(s.set.date) }} · {{ s.photo.number }} of {{ s.set.photos.length }}@if (s.photo.caption) { · {{ s.photo.caption }} }</span>
                <button type="button" class="btn" (click)="step(1)" [disabled]="!canStep(1)" aria-label="Next photo">›</button>
                <button type="button" class="btn primary" (click)="close()">Close</button>
              </div>
            </div>
          }
        </dialog>
      } @else if (view.error(); as err) {
        <app-state kind="error" [message]="err" (retry)="view.load()" />
      } @else {
        <app-state kind="loading" [blocks]="2" />
      }
    </div>
  `,
  styles: `
    .hist { margin-top: 12px; padding-top: 4px; border-top: 1px solid var(--divider); }
    .hist > li.kv { padding: 8px 0; border-top: 0; }
    .hist > li.kv + li.kv { border-top: 1px solid var(--divider); }
    .sub { margin: 0 0 12px; }
    .set + .set { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--divider); }
    .set-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .thumbs { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 8px; }
    .thumb { position: relative; display: block; padding: 0; aspect-ratio: 3 / 4; overflow: hidden;
      border-radius: var(--radius-inner); background: var(--inset); }
    .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .thumb:focus-visible { outline: 2px solid var(--info); outline-offset: 2px; }
    .cap { position: absolute; left: 6px; bottom: 6px; padding: 1px 6px; border-radius: 6px;
      background: rgba(11, 11, 11, .6); color: #fff; }
    .viewer { padding: 0; border: 0; background: transparent; max-width: min(96vw, 720px); max-height: 96dvh; }
    .viewer::backdrop { background: rgba(0, 0, 0, .8); }
    .frame { display: grid; gap: 8px; }
    .frame img { max-width: 100%; max-height: calc(96dvh - 64px); object-fit: contain; border-radius: var(--radius-inner);
      margin: 0 auto; display: block; }
    .bar { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: var(--radius);
      background: var(--container); color: var(--text); }
    .grow { flex: 1; min-width: 0; }
    @media (min-width: 900px) { .stack { max-width: 640px; } }
  `,
})
export class MeasurementsPage {
  private readonly api = inject(CoachApi);
  protected readonly view = viewResource<MeasurementsView>('setup/measurements');
  protected readonly edit = new EditState();
  protected readonly cm = signal('');
  protected readonly date = signal('');
  protected readonly shown = signal<{ set: PhotoSet; photo: Photo } | null>(null);
  private readonly viewer = viewChild<ElementRef<HTMLDialogElement>>('viewer');

  protected readonly allPhotos = computed(() =>
    (this.view.data()?.photos.sets ?? []).flatMap((set) => set.photos.map((photo) => ({ set, photo }))));

  constructor() {
    this.view.load();
  }

  protected value(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  protected day(d: string): string {
    return dayLabel(d);
  }

  protected cmText(cm: number): string {
    return `${fmt(cm, cm % 1 ? 1 : 0)} cm`;
  }

  protected history(v: MeasurementsView): { date: string; cm: number; start: boolean }[] {
    const rows = v.waist.values.map((w) => ({ ...w, start: false }));
    if (v.waist.start) rows.push({ ...v.waist.start, start: true });
    return rows;
  }

  protected latest(v: MeasurementsView): string {
    const w = v.waist.values[0] ?? v.waist.start;
    return w ? this.cmText(w.cm) : '';
  }

  protected waistDue(v: MeasurementsView): string {
    return v.waist.next_due ? `Next due ${dayLabel(v.waist.next_due)}` : '';
  }

  protected photoLine(v: MeasurementsView): string {
    const p = v.photos;
    if (p.enabled === null) return '';
    if (!p.enabled) return 'Photo check-ins off';
    return p.next_due ? `Next set due ${dayLabel(p.next_due)}` : '';
  }

  protected startWaist(v: MeasurementsView): void {
    this.cm.set('');
    this.date.set(v.today);
    this.edit.start('waist');
  }

  protected saveWaist(): void {
    const raw = this.cm().trim().replace(',', '.');
    const body = { cm: raw === '' ? null : Number(raw), date: this.date() || null };
    this.edit.save('waist', this.api.command<MeasurementsView>('setup/measurements/waist', body), (v) => {
      this.view.data.set(v);
      return 'Saved.';
    });
  }

  protected src(p: Photo): string {
    return `${CoachApi.BASE}/${p.url}`;
  }

  protected alt(s: PhotoSet, p: Photo): string {
    return `Photo ${p.number} of the ${dayLabel(s.date, false)} set${p.caption ? ` (${p.caption})` : ''}`;
  }

  protected open(set: PhotoSet, photo: Photo): void {
    this.shown.set({ set, photo });
    this.viewer()?.nativeElement.showModal();
  }

  protected close(): void {
    this.viewer()?.nativeElement.close();
  }

  protected closeOnBackdrop(e: MouseEvent): void {
    if (e.target === this.viewer()?.nativeElement) this.close();
  }

  private index(): number {
    const s = this.shown();
    return s ? this.allPhotos().findIndex((x) => x.set.date === s.set.date && x.photo.number === s.photo.number) : -1;
  }

  protected canStep(d: number): boolean {
    const i = this.index() + d;
    return i >= 0 && i < this.allPhotos().length;
  }

  protected step(d: number): void {
    if (this.canStep(d)) this.shown.set(this.allPhotos()[this.index() + d]);
  }
}
