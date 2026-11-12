import { InputSignal, Type } from '@angular/core';
import { WeekIntakeBlock } from './blocks/week-intake-block';
import { WeekNotesBlock } from './blocks/week-notes-block';
import { WeekStepsBlock } from './blocks/week-steps-block';
import { WeekTrainingBlock } from './blocks/week-training-block';
import { WeekWeightBlock } from './blocks/week-weight-block';
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
  WeekWeightBlock, WeekIntakeBlock, WeekTrainingBlock, WeekStepsBlock, WeekNotesBlock,
];
