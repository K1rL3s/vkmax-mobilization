import type { components } from "@/shared/api/schema/generated";
import { formatDay, formatTime } from "@/shared/lib/format";

type Works = components["schemas"]["AnnouncementWorks"];

const isSameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

export const announcementWhen = (iso: string) => {
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

export const worksState = ({ starts_at: startsAt, ends_at: endsAt }: Works) => {
  const now = Date.now();

  if (now < Date.parse(startsAt)) {
    return "planned";
  }

  return now < Date.parse(endsAt) ? "going" : "done";
};

export const worksPeriod = ({
  starts_at: startsAt,
  ends_at: endsAt,
}: Works) => {
  const isSameDay =
    new Date(startsAt).toDateString() === new Date(endsAt).toDateString();
  const end = isSameDay
    ? formatTime(endsAt)
    : `${formatDay(endsAt)}, ${formatTime(endsAt)}`;

  return `${formatDay(startsAt)}, ${formatTime(startsAt)} - ${end}`;
};
