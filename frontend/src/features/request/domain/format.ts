import { duration } from "@/shared/lib/format";

export const deadlineLeft = (deadlineAt: string | null | undefined) => {
  if (!deadlineAt) {
    return null;
  }

  const left = new Date(deadlineAt).getTime() - Date.now();

  return left >= 0
    ? { overdue: false, text: `Осталось ${duration(left)}` }
    : { overdue: true, text: `Просрочена на ${duration(-left)}` };
};

export const deadlineProgress = (
  createdAt: string,
  deadlineAt: string | null | undefined,
) => {
  if (!deadlineAt) {
    return null;
  }

  const start = new Date(createdAt).getTime();
  const end = new Date(deadlineAt).getTime();

  if (end <= start) {
    return null;
  }

  return Math.min(1, Math.max(0, (Date.now() - start) / (end - start)));
};
