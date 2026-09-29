export const maskDate = (text: string): string => {
  const digits = text.replace(/\D/g, "").slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)]
    .filter(Boolean)
    .join(".");
};

export const isoFromMasked = (masked: string): string => {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(masked);
  if (!match) return "";
  const [, day, month, year] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return date.getUTCDate() === Number(day) &&
    date.getUTCMonth() === Number(month) - 1
    ? `${year}-${month}-${day}`
    : "";
};

export const maskedFromIso = (iso: string): string =>
  /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso.split("-").reverse().join(".") : "";
