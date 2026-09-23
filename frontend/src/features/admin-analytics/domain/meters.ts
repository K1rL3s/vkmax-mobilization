const MONTHS = [
  "январь",
  "февраль",
  "март",
  "апрель",
  "май",
  "июнь",
  "июль",
  "август",
  "сентябрь",
  "октябрь",
  "ноябрь",
  "декабрь",
];

const DAY_MONTHS = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

// даты сезона разбираются строкой по той же причине, что и недели графика
export const periodTitle = (iso: string): string => {
  const [year, month] = iso.split("-");

  return `${MONTHS[Number(month) - 1]} ${year}`;
};

export const windowTitle = (from: string, to: string): string => {
  const [, fromMonth, fromDay] = from.split("-");
  const [, toMonth, toDay] = to.split("-");

  return fromMonth === toMonth
    ? `с ${Number(fromDay)} по ${Number(toDay)} ${DAY_MONTHS[Number(toMonth) - 1]}`
    : `с ${Number(fromDay)} ${DAY_MONTHS[Number(fromMonth) - 1]} по ${Number(toDay)} ${DAY_MONTHS[Number(toMonth) - 1]}`;
};
