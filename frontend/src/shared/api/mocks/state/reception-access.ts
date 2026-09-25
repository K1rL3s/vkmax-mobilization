import type { components } from "../../schema/generated";

import { address, findFlat, findHouse, houseFlats } from "./houses";
import { residencyForHouse } from "./profile";
import {
  DAY,
  MINUTE,
  at,
  fromOrgNaive,
  isoDate,
  orgOf,
  startOfToday,
  weekdayAfter,
} from "./reception-time";

type Schemas = components["schemas"];

type MockAccessTarget = {
  flat_id: number;
  flat_number: string;
  slot_id: number | null;
  responded_at: string | null;
};

type MockAccessRequest = {
  id: number;
  created_at: string;
  house_id: number;
  reason: string;
  date: string;
  slots: { id: number; starts_at: string; capacity: number }[];
  targets: MockAccessTarget[];
};

const seedAccessRequests = (): MockAccessRequest[] => {
  const day = weekdayAfter(3);
  // квартира 12 остаётся без ответа: её занимает мок-житель по рецепту посева,
  // и окно он выбирает сам. Окно 12 забито под завязку соседями - на нём
  // проверяется «мест больше нет»
  const responses: Record<string, number> = {
    "45": 11,
    "112": 11,
    "7": 12,
    "28": 12,
    "63": 12,
    "90": 13,
  };

  const passed = new Date(startOfToday().getTime() - 9 * DAY);

  return [
    {
      id: 1,
      created_at: new Date(Date.now() - DAY).toISOString(),
      house_id: 1,
      reason:
        "Плановая проверка газового оборудования: мастер осмотрит плиту и подводку, займёт 15 минут",
      date: isoDate(day),
      slots: [9, 12, 15, 18].map((hour, index) => ({
        id: 11 + index,
        starts_at: at(day, hour),
        capacity: 3,
      })),
      targets: houseFlats(1, "").map((flat) => ({
        flat_id: flat.id,
        flat_number: flat.number,
        slot_id: responses[flat.number] ?? null,
        responded_at:
          flat.number in responses
            ? new Date(Date.now() - 12 * 60 * MINUTE).toISOString()
            : null,
      })),
    },
    // прошедший сбор: сборы на бэке не удаляются и не архивируются, поэтому
    // кабинет УК должен разводить идущие и прошлые с первого же экрана
    {
      id: 2,
      created_at: new Date(Date.now() - 11 * DAY).toISOString(),
      house_id: 1,
      reason: "Замена стояка холодной воды в первом подъезде",
      date: isoDate(passed),
      slots: [10, 13].map((hour, index) => ({
        id: 21 + index,
        starts_at: at(passed, hour),
        capacity: 2,
      })),
      targets: houseFlats(1, "")
        .slice(0, 4)
        .map((flat, index) => ({
          flat_id: flat.id,
          flat_number: flat.number,
          slot_id: index < 3 ? 21 + (index % 2) : null,
          responded_at:
            index < 3 ? new Date(Date.now() - 10 * DAY).toISOString() : null,
        })),
    },
  ];
};

const state = {
  accessRequests: seedAccessRequests(),
  nextId: 10,
  nextSlotId: 100,
};

export const resetReceptionAccess = (): void => {
  state.accessRequests = seedAccessRequests();
  state.nextId = 10;
  state.nextSlotId = 100;
};

const slotTaken = (item: MockAccessRequest, slotId: number) =>
  item.targets.filter((target) => target.slot_id === slotId).length;

const myTarget = (item: MockAccessRequest) => {
  const flatId = residencyForHouse(item.house_id)?.flat_id ?? null;

  return flatId === null
    ? undefined
    : item.targets.find((target) => target.flat_id === flatId);
};

export const accessRequestItem = (
  item: MockAccessRequest,
): Schemas["AccessRequestItem"] => {
  const house = findHouse(item.house_id);

  return {
    id: item.id,
    created_at: item.created_at,
    house_id: item.house_id,
    address: house ? address(house) : "",
    reason: item.reason,
    date: item.date,
    slots: item.slots.map((slot) => ({
      ...slot,
      taken: slotTaken(item, slot.id),
    })),
    responded_count: item.targets.filter((target) => target.slot_id !== null)
      .length,
    targets_count: item.targets.length,
    my_flat_id: residencyForHouse(item.house_id)?.flat_id ?? null,
    my_slot_id: myTarget(item)?.slot_id ?? null,
  };
};

// квартиры без ячейки бэк отдаёт только в ответе на создание, поэтому
// список сюда передаёт создающая ручка, а чтение сбора возвращает пустой
export const accessRequestGrid = (
  item: MockAccessRequest,
  flatsWithoutResidents: number[] = [],
): Schemas["AccessRequestGrid"] => ({
  access_request: accessRequestItem(item),
  targets: item.targets,
  flats_without_residents: flatsWithoutResidents,
});

export const houseAccessRequests = (
  houseId: number,
): Schemas["AccessRequestItem"][] =>
  state.accessRequests
    .filter((item) => item.house_id === houseId)
    .map(accessRequestItem);

export const orgAccessRequests = (
  orgId: number,
): Schemas["AccessRequestItem"][] =>
  state.accessRequests
    .filter((item) => orgOf(item.house_id) === orgId)
    .map(accessRequestItem)
    // идущие сборы впереди архива
    .sort((a, b) => b.date.localeCompare(a.date));

export const findAccessRequest = (
  accessRequestId: number,
): MockAccessRequest | undefined =>
  state.accessRequests.find((item) => item.id === accessRequestId);

export const chooseAccessSlot = (
  item: MockAccessRequest,
  slotId: number,
): "no-slot" | "full" | "ok" => {
  const slot = item.slots.find((candidate) => candidate.id === slotId);
  const flatId = residencyForHouse(item.house_id)?.flat_id ?? null;
  const flat = flatId === null ? undefined : findFlat(flatId);

  if (!slot || !flat) {
    return "no-slot";
  }

  // сбор сеется на квартиры дома, а мок заводит квартиру только после
  // подтверждения: житель, попавший в дом позже, дописывается в цели сам
  const target = myTarget(item) ?? {
    flat_id: flat.id,
    flat_number: flat.number,
    slot_id: null,
    responded_at: null,
  };

  if (target.slot_id !== slotId) {
    if (slotTaken(item, slotId) >= slot.capacity) {
      return "full";
    }

    target.slot_id = slotId;
    target.responded_at = new Date().toISOString();
  }

  if (!item.targets.includes(target)) {
    item.targets.push(target);
  }

  return "ok";
};

// ячейку получает только квартира с подтверждённым жителем: кого взял бы бэк,
// решает вызывающая ручка, здесь остаётся разложить их по сбору
export const createAccessRequest = (
  body: Schemas["CreateAccessRequestRequest"],
  eligible: { flat_id: number; flat_number: string }[],
): Schemas["AccessRequestGrid"] => {
  const created: MockAccessRequest = {
    id: state.nextId++,
    created_at: new Date().toISOString(),
    house_id: body.house_id,
    reason: body.reason,
    date: body.date,
    slots: body.slots.map((slot) => ({
      id: state.nextSlotId++,
      starts_at: fromOrgNaive(slot.starts_at),
      capacity: slot.capacity,
    })),
    targets: eligible.map((flat) => ({
      ...flat,
      slot_id: null,
      responded_at: null,
    })),
  };
  state.accessRequests.push(created);

  return accessRequestGrid(
    created,
    body.flat_ids.filter(
      (flatId) => !eligible.some((flat) => flat.flat_id === flatId),
    ),
  );
};
