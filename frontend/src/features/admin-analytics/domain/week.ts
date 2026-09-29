const dayMonth = (day: Date) =>
  `${String(day.getUTCDate()).padStart(2, "0")}.${String(day.getUTCMonth() + 1).padStart(2, "0")}`;

export const weekRange = (monday: string) => {
  const start = new Date(`${monday}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 6);

  const withYear = start.getUTCFullYear() !== end.getUTCFullYear();
  const format = (day: Date) =>
    withYear ? `${dayMonth(day)}.${day.getUTCFullYear()}` : dayMonth(day);

  return `${format(start)}-${format(end)}`;
};
