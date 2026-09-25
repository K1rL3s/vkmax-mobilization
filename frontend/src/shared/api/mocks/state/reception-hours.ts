import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

let windows = [0, 1, 2, 3, 4].flatMap((weekday) =>
  [
    { time_from: "09:00", time_to: "13:00" },
    { time_from: "14:00", time_to: "18:00" },
  ].map((window, index) => ({
    ...window,
    id: weekday * 2 + index + 1,
    org_id: 1,
    weekday,
    slot_minutes: 30,
    capacity: 1,
  })),
);

export const windowsOn = (orgId: number, weekday: number) =>
  windows.filter(
    (window) => window.org_id === orgId && window.weekday === weekday,
  );

export const receptionWindows = (
  orgId: number,
): Schemas["ReceptionWindowItem"][] =>
  windows
    .filter((window) => window.org_id === orgId)
    .map((window) => ({
      id: window.id,
      weekday: window.weekday,
      time_from: window.time_from,
      time_to: window.time_to,
      slot_minutes: window.slot_minutes,
      capacity: window.capacity,
    }))
    .sort(
      (a, b) => a.weekday - b.weekday || a.time_from.localeCompare(b.time_from),
    );

export const setReceptionWindows = (
  orgId: number,
  replacement: Schemas["ReceptionWindowInput"][],
): Schemas["ReceptionWindowItem"][] => {
  let nextId = Math.max(0, ...windows.map((window) => window.id));

  windows = [
    ...windows.filter((window) => window.org_id !== orgId),
    ...replacement.map((window) => ({
      ...window,
      org_id: orgId,
      id: ++nextId,
    })),
  ];

  return receptionWindows(orgId);
};
