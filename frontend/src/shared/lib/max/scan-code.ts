import { z } from "zod";

const scanned = z.union([
  z.string(),
  z.object({ value: z.string() }).transform(({ value }) => value),
]);

export const canScanCode = () =>
  Boolean(window.WebApp?.openCodeReader) &&
  ["ios", "android"].includes(window.WebApp?.platform ?? "");

export const scanCode = async (): Promise<string | null> => {
  try {
    const result = await window.WebApp?.openCodeReader?.(true);

    return scanned.safeParse(result).data || null;
  } catch {
    return null;
  }
};
