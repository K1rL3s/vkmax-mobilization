import { formatDay } from "@/shared/lib/format";

const monthFormat = new Intl.DateTimeFormat("ru-RU", { month: "long" });

export const periodTitle = (iso: string): string =>
  `${monthFormat.format(new Date(`${iso}T00:00`))} ${iso.slice(0, 4)}`;

export const windowTitle = (from: string, to: string): string => {
  const [, fromMonth, fromDay] = from.split("-");
  const toTitle = formatDay(`${to}T00:00`);

  return fromMonth === to.split("-")[1]
    ? `с ${Number(fromDay)} по ${toTitle}`
    : `с ${formatDay(`${from}T00:00`)} по ${toTitle}`;
};
