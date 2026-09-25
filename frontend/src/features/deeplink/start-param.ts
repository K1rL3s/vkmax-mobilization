import { z } from "zod";

const startParam = (pattern: RegExp) => z.string().max(512).regex(pattern);

const positiveInteger = (value: string): number | null => {
  const parsed = Number(value);

  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
};

const houseStartParamSchema = startParam(/^house_([1-9]\d*)$/).transform(
  (raw, context) => {
    const houseId = positiveInteger(raw.slice("house_".length));

    if (houseId === null) {
      context.addIssue({ code: "custom", message: "Некорректный ID дома" });
      return z.NEVER;
    }

    return { kind: "house", houseId } as const;
  },
);

const qrStartParamPattern = /^qr_([1-9]\d*)_([1-9]\d*)$/;

const qrStartParamSchema = startParam(qrStartParamPattern).transform(
  (raw, context) => {
    const match = qrStartParamPattern.exec(raw);
    const houseId = positiveInteger(match?.[1] ?? "");
    const entrance = positiveInteger(match?.[2] ?? "");

    if (houseId === null || entrance === null) {
      context.addIssue({ code: "custom", message: "Некорректный QR-параметр" });
      return z.NEVER;
    }

    return { kind: "qr", houseId, entrance } as const;
  },
);

const codeStartParamSchema = <Kind extends string>(
  prefix: string,
  kind: Kind,
) =>
  startParam(new RegExp(`^${prefix}_[A-Za-z0-9_-]+$`)).transform((raw) => ({
    kind,
    code: raw.slice(prefix.length + 1),
  }));

const demoStartParamPattern = /^demo_(admin|staff|resident)_([1-5])$/;

const demoStartParamSchema = startParam(demoStartParamPattern).transform(
  (raw) => {
    const [, cabinet, profile] = demoStartParamPattern.exec(raw) ?? [];

    return {
      kind: "demo" as const,
      cabinet: cabinet as "admin" | "staff" | "resident",
      profile: Number(profile),
    };
  },
);

const startParamSchema = z.union([
  houseStartParamSchema,
  qrStartParamSchema,
  codeStartParamSchema("flat", "flat"),
  codeStartParamSchema("inv", "invite"),
  codeStartParamSchema("reg", "register"),
  demoStartParamSchema,
]);

export type StartParam = z.infer<typeof startParamSchema>;

export const parseStartParam = (raw: string | null): StartParam | null => {
  const parsed = startParamSchema.safeParse(raw);

  return parsed.success ? parsed.data : null;
};
