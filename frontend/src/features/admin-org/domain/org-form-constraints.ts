export const orgFormConstraints = {
  dayMin: 1,
  dayMax: 28,
  thresholdMin: 2,
  thresholdMax: 100,
  windowHoursMin: 1,
  windowHoursMax: 168,
  phone: 32,
  email: 120,
  site: 200,
  receptionNote: 300,
};

export const isSiteAddress = (value: string) =>
  /^[\p{L}\p{N}\p{M}_-]+(\.[\p{L}\p{N}\p{M}_-]+)+\.?([/?#]|$)/u.test(
    value.replace(/^https?:\/\//i, ""),
  );
