// моменты для посева: всё, что лежит в моке, отсчитывается от «сейчас»,
// иначе демо-данные стареют. Пояс организации - в `reception-time.ts`

export const period = (monthsBack: number): string => {
  const today = new Date();
  const month = new Date(today.getFullYear(), today.getMonth() - monthsBack, 1);

  return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-01`;
};

export const minutes = (count: number) =>
  new Date(Date.now() + count * 60 * 1000).toISOString();

export const days = (count: number) => minutes(count * 24 * 60);

export const shift = (iso: string, addMinutes: number) =>
  new Date(new Date(iso).getTime() + addMinutes * 60 * 1000).toISOString();

export const today = (): string => new Date().toISOString().slice(0, 10);
