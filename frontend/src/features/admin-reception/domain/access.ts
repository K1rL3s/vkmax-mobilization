import type { components } from "@/shared/api/schema/generated";

import { dayKey } from "./day";

export type AccessRequest = components["schemas"]["AccessRequestItem"];

export type AccessSlot = components["schemas"]["AccessSlotItem"];

export type AccessTarget = components["schemas"]["AccessTargetCell"];

// сбор идёт, пока не прошёл его день: ни отмены, ни правки на бэке нет,
// других состояний у сбора не бывает. Сборы не удаляются и не архивируются,
// поэтому без этого деления список с первой недели превращается в архив
export const splitAccessRequests = (items: AccessRequest[]) => {
  const today = dayKey(new Date());

  return {
    active: items.filter((item) => item.date >= today),
    past: items.filter((item) => item.date < today),
  };
};

export const respondedLabel = (item: AccessRequest): string =>
  `ответили ${item.responded_count} из ${item.targets_count}`;

export type AccessGrid = components["schemas"]["AccessRequestGrid"];

export type AccessWindow = {
  slot: AccessSlot;
  flats: AccessTarget[];
};

// номера квартир читаются как маршрут на день, поэтому в окне они идут по
// возрастанию, а не в порядке, в котором жители отвечали
const byFlatNumber = (a: AccessTarget, b: AccessTarget) =>
  Number(a.flat_number) - Number(b.flat_number) ||
  a.flat_number.localeCompare(b.flat_number);

export const accessWindows = (grid: AccessGrid): AccessWindow[] =>
  grid.access_request.slots.map((slot) => ({
    slot,
    flats: grid.targets
      .filter((target) => target.slot_id === slot.id)
      .sort(byFlatNumber),
  }));

export const unansweredFlats = (grid: AccessGrid): AccessTarget[] =>
  grid.targets.filter((target) => target.slot_id === null).sort(byFlatNumber);

export const placesLeftLabel = (window: AccessWindow): string => {
  const left = window.slot.capacity - window.flats.length;

  return left > 0 ? `свободно ${left} из ${window.slot.capacity}` : "мест нет";
};
