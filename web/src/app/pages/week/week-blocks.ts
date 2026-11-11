import { InputSignal, Type } from '@angular/core';
import { WeekView } from './week.types';

/**
 * A Week number block: a component that takes the whole Week view and
 * renders its own card, or nothing when its part is missing. Blocks sit
 * between the decision (with its proposals) and the collapsed report.
 */
export interface WeekBlock {
  readonly view: InputSignal<WeekView>;
}

/** Week's number blocks in page order (spec, stories 45-48). */
export const WEEK_BLOCKS: Type<WeekBlock>[] = [
  // weight, intake, training, notes and flags (ticket 07)
];
