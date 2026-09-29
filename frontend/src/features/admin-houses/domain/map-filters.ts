import type { MapTone } from "@/shared/ui/map";

export const STATES = [
  { id: "emergency", label: "Авария", tone: "red" },
  { id: "escalated", label: "Эскалация", tone: "orange" },
  { id: "overdue", label: "Просрочено", tone: "yellow" },
  { id: "open", label: "Открыто", tone: "blue" },
  { id: "calm", label: "Спокойно", tone: "green" },
] as const satisfies readonly { id: string; label: string; tone: MapTone }[];

export const metersTone = (percent: number | null | undefined): MapTone =>
  percent == null
    ? "muted"
    : percent >= 8000
      ? "green"
      : percent >= 5000
        ? "yellow"
        : "red";

export const residentsTone = (
  residents: number | null | undefined,
  flats: number | null | undefined,
): MapTone =>
  residents == null || !flats
    ? "muted"
    : residents * 10 >= flats * 3
      ? "green"
      : residents * 10 >= flats
        ? "yellow"
        : "red";

export const parseRange = (
  value: string | null | undefined,
  scale: number,
): [number | undefined, number | undefined] => {
  const match = /^(\d*)-(\d*)$/.exec(value ?? "");
  if (!match) return [undefined, undefined];
  const bound = (part: string) =>
    part === "" ? undefined : Number(part) * scale;
  return [bound(match[1]), bound(match[2])];
};

export const houseSignature = (house: {
  open: number;
  overdue: number;
  escalated: number;
  urgent_id?: number | null;
  poll_id?: number | null;
  appointments_today: number;
}) =>
  [
    house.open,
    house.overdue,
    house.escalated,
    house.urgent_id ?? 0,
    house.poll_id ?? 0,
    house.appointments_today,
  ].join(":");
