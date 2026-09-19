import { duration } from "@/shared/lib/format";

/**
 * Нормативный срок словами: сколько осталось или насколько заявка просрочена.
 * Срока может не быть - категория задаёт его не всегда.
 */
export const deadlineLeft = (
  deadlineAt: string | null | undefined,
  now = Date.now(),
) => {
  if (!deadlineAt) {
    return null;
  }

  const left = new Date(deadlineAt).getTime() - now;

  if (Number.isNaN(left)) {
    return null;
  }

  return left >= 0
    ? { overdue: false, text: `Осталось ${duration(left)}` }
    : { overdue: true, text: `Просрочена на ${duration(-left)}` };
};

/**
 * Доля нормативного срока, которая уже прошла: 0 - заявку только подали,
 * 1 - срок вышел. Из неё рисуется полоса на Главной.
 */
export const deadlineProgress = (
  createdAt: string,
  deadlineAt: string | null | undefined,
  now = Date.now(),
) => {
  if (!deadlineAt) {
    return null;
  }

  const start = new Date(createdAt).getTime();
  const end = new Date(deadlineAt).getTime();

  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) {
    return null;
  }

  return Math.min(1, Math.max(0, (now - start) / (end - start)));
};
