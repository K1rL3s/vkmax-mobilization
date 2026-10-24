import type { components } from "@/shared/api/schema/generated";
import { formatDay, formatTime } from "@/shared/lib/format";

type Works = components["schemas"]["AnnouncementWorks"];
type Announcement = components["schemas"]["AnnouncementItem"];

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

const ARCHIVE_WINDOW_DAYS = 30;

export const isArchived = ({
  created_at: createdAt,
  works,
}: Pick<Announcement, "created_at" | "works">) => {
  if (works && worksState(works) !== "done") {
    return false;
  }

  const cutoff = Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  return Date.parse(createdAt) < cutoff;
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
