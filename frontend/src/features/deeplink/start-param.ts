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

const flatStartParamSchema = startParam(/^flat_[A-Za-z0-9_-]+$/).transform(
  (raw) => ({
    kind: "flat" as const,
    code: raw.slice("flat_".length),
  }),
);

const inviteStartParamSchema = startParam(/^inv_[A-Za-z0-9_-]+$/).transform(
  (raw) => ({
    kind: "invite" as const,
    code: raw.slice("inv_".length),
  }),
);

const registerStartParamSchema = startParam(/^reg_[A-Za-z0-9_-]+$/).transform(
  (raw) => ({
    kind: "register" as const,
    code: raw.slice("reg_".length),
  }),
);

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
  flatStartParamSchema,
  inviteStartParamSchema,
  registerStartParamSchema,
  demoStartParamSchema,
]);

export type StartParam = z.infer<typeof startParamSchema>;

export const parseStartParam = (raw: string | null): StartParam | null => {
  const parsed = startParamSchema.safeParse(raw);

  return parsed.success ? parsed.data : null;
};
