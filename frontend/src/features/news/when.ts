import { formatDay, formatTime } from "@/shared/lib/format";

const isSameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

export const newsWhen = (iso: string) => {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (isSameDay(date, today)) {
    return `сегодня, ${formatTime(iso)}`;
  }

  if (isSameDay(date, yesterday)) {
    return `вчера, ${formatTime(iso)}`;
  }

  return date.getFullYear() === today.getFullYear()
    ? formatDay(iso)
    : `${formatDay(iso)} ${date.getFullYear()}`;
};
