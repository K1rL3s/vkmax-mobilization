import type { components } from "../../schema/generated";

import { addressOf, findFlat, houseFlats, orgOf } from "./houses";
import { residencyForHouse } from "./profile";
import {
  DAY,
  at,
  days,
  fromOrgNaive,
  hours,
  isoDate,
  startOfToday,
  weekdayAfter,
} from "./time";

type Schemas = components["schemas"];

type MockAccessRequest = {
  id: number;
  created_at: string;
  house_id: number;
  reason: string;
  date: string;
  slots: { id: number; starts_at: string; capacity: number }[];
  targets: {
    flat_id: number;
    flat_number: string;
    slot_id: number | null;
    responded_at: string | null;
  }[];
};

const day = weekdayAfter(3);

const passed = new Date(startOfToday().getTime() - 9 * DAY);

const responses: Record<string, number> = {
  "45": 11,
  "112": 11,
  "7": 12,
  "28": 12,
  "63": 12,
  "90": 13,
};

const accessRequests: MockAccessRequest[] = [
  {
    id: 1,
    created_at: days(-1),
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
      responded_at: flat.number in responses ? hours(-12) : null,
    })),
  },
  {
    id: 2,
    created_at: days(-11),
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
        responded_at: index < 3 ? days(-10) : null,
      })),
  },
];

let nextId = 10;

let nextSlotId = 100;

const slotTaken = (item: MockAccessRequest, slotId: number) =>
  item.targets.filter((target) => target.slot_id === slotId).length;

const myFlatId = (item: MockAccessRequest) =>
  residencyForHouse(item.house_id)?.flat_id ?? null;

export const accessRequestItem = (
  item: MockAccessRequest,
): Schemas["AccessRequestItem"] => {
  const flatId = myFlatId(item);

  return {
    id: item.id,
    created_at: item.created_at,
    house_id: item.house_id,
    address: addressOf(item.house_id),
    reason: item.reason,
    date: item.date,
    slots: item.slots.map((slot) => ({
      ...slot,
      taken: slotTaken(item, slot.id),
    })),
    responded_count: item.targets.filter((target) => target.slot_id !== null)
      .length,
    targets_count: item.targets.length,
    my_flat_id: flatId,
    my_slot_id:
      item.targets.find((target) => target.flat_id === flatId)?.slot_id ?? null,
  };
};

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
  accessRequests
    .filter((item) => item.house_id === houseId)
    .map(accessRequestItem);

export const orgAccessRequests = (
  orgId: number,
): Schemas["AccessRequestItem"][] =>
  accessRequests
    .filter((item) => orgOf(item.house_id) === orgId)
    .map(accessRequestItem)
    .sort((a, b) => b.date.localeCompare(a.date));

export const findAccessRequest = (
  accessRequestId: number,
): MockAccessRequest | undefined =>
  accessRequests.find((item) => item.id === accessRequestId);

export const chooseAccessSlot = (
  item: MockAccessRequest,
  slotId: number,
): "no-slot" | "full" | "ok" => {
  const slot = item.slots.find((candidate) => candidate.id === slotId);
  const flatId = myFlatId(item);
  const flat = flatId === null ? undefined : findFlat(flatId);

  if (!slot || !flat) {
    return "no-slot";
  }

  const target = item.targets.find((target) => target.flat_id === flat.id) ?? {
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

export const createAccessRequest = (
  body: Schemas["CreateAccessRequestRequest"],
  eligible: { flat_id: number; flat_number: string }[],
): Schemas["AccessRequestGrid"] => {
  const created: MockAccessRequest = {
    id: nextId++,
    created_at: new Date().toISOString(),
    house_id: body.house_id,
    reason: body.reason,
    date: body.date,
    slots: body.slots.map((slot) => ({
      id: nextSlotId++,
      starts_at: fromOrgNaive(slot.starts_at),
      capacity: slot.capacity,
    })),
    targets: eligible.map((flat) => ({
      ...flat,
      slot_id: null,
      responded_at: null,
    })),
  };
  accessRequests.push(created);

  return accessRequestGrid(
    created,
    body.flat_ids.filter(
      (flatId) => !eligible.some((flat) => flat.flat_id === flatId),
    ),
  );
};
