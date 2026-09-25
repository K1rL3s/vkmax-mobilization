import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

type MockReceptionWindow = Schemas["ReceptionWindowItem"] & { org_id: number };

// приём ведёт только первая УК: дом чужой организации показывает жителю экран
// без приёма
const seedWindows = (): MockReceptionWindow[] =>
  [0, 1, 2, 3, 4].flatMap((weekday) =>
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

const state = { windows: seedWindows() };

export const resetReceptionHours = (): void => {
  state.windows = seedWindows();
};

export const windowsOn = (
  orgId: number,
  weekday: number,
): MockReceptionWindow[] =>
  state.windows.filter(
    (window) => window.org_id === orgId && window.weekday === weekday,
  );

export const receptionWindows = (
  orgId: number,
): Schemas["ReceptionWindowItem"][] =>
  state.windows
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

// `PUT` заменяет сетку организации целиком: два окна в один день - это
// перерыв, пустой список - приёма нет вовсе
export const setReceptionWindows = (
  orgId: number,
  windows: Schemas["ReceptionWindowInput"][],
): Schemas["ReceptionWindowItem"][] => {
  let nextId = Math.max(0, ...state.windows.map((window) => window.id));

  state.windows = [
    ...state.windows.filter((window) => window.org_id !== orgId),
    ...windows.map((window) => ({ ...window, org_id: orgId, id: ++nextId })),
  ];

  return receptionWindows(orgId);
};
