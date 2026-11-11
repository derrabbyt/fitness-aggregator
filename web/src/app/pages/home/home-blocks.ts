import { InputSignal, Type } from '@angular/core';
import { ActivitiesBlock } from './blocks/activities-block';
import { FoodBlock } from './blocks/food-block';
import { GymBlock } from './blocks/gym-block';
import { SleepBlock } from './blocks/sleep-block';
import { StepsBlock } from './blocks/steps-block';
import { HomeView } from './home.types';

/**
 * A Home block: a component that takes the whole Home view and the day's
 * query params (for links to its detail) and renders its own card, or
 * nothing when its part is missing.
 */
export interface HomeBlock {
  readonly view: InputSignal<HomeView>;
  readonly dayQuery: InputSignal<Record<string, string | null>>;
}

/** Home's blocks in page order: food, weight, steps, training, sleep (spec, story 14). */
export const HOME_BLOCKS: Type<HomeBlock>[] = [
  FoodBlock,
  // weight (ticket 03)
  StepsBlock,
  GymBlock,
  ActivitiesBlock,
  SleepBlock,
];
