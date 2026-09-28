import { matchPath } from "react-router-dom";
import { z } from "zod";

import { requestCategorySchema } from "@/features/request";
import { Routes } from "@/shared/model/routes";

const startParam = (pattern: RegExp) => z.string().max(512).regex(pattern);

const positiveInteger = (value: string): number | null => {
  const parsed = Number(value);

  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
};

const houseStartParamPattern = /^house_([1-9]\d*)(?:_([a-z_]+))?$/;

const houseStartParamSchema = startParam(houseStartParamPattern).transform(
  (raw, context) => {
    const [, id = "", rawCategory] = houseStartParamPattern.exec(raw) ?? [];
    const houseId = positiveInteger(id);
    const category =
      rawCategory === undefined
        ? null
        : (requestCategorySchema.safeParse(rawCategory).data ?? undefined);

    if (houseId === null || category === undefined) {
      context.addIssue({
        code: "custom",
        message: "Некорректная ссылка на дом",
      });
      return z.NEVER;
    }

    return { kind: "house", houseId, category } as const;
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

const decodeBase64Url = (raw: string): unknown => {
  try {
    const base64 = raw.replaceAll("-", "+").replaceAll("_", "/");
    const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));

    return JSON.parse(
      new TextDecoder().decode(
        Uint8Array.from(binary, (char) => char.charCodeAt(0)),
      ),
    );
  } catch {
    return null;
  }
};

const linkableRoutes = Object.values(Routes).filter(
  (route) =>
    route !== Routes.WELCOME &&
    route !== Routes.DEEPLINK &&
    route !== Routes.OUTSIDE_MAX,
);

const appPathSchema = z
  .string()
  .regex(/^\/[A-Za-z0-9_-]+(\/[A-Za-z0-9_-]+)*$/)
  .refine((path) =>
    linkableRoutes.some((route) => matchPath(route, path) !== null),
  );

const pathStartParamSchema = startParam(/^[A-Za-z0-9_-]+$/).transform(
  (raw, context) => {
    const payload = z
      .object({ path: appPathSchema })
      .safeParse(decodeBase64Url(raw));

    if (!payload.success) {
      context.addIssue({ code: "custom", message: "Некорректный путь" });
      return z.NEVER;
    }

    return { kind: "path", path: payload.data.path } as const;
  },
);

const startParamSchema = z.union([
  houseStartParamSchema,
  qrStartParamSchema,
  codeStartParamSchema("flat", "flat"),
  codeStartParamSchema("inv", "invite"),
  codeStartParamSchema("reg", "register"),
  demoStartParamSchema,
  pathStartParamSchema,
]);

export type StartParam = z.infer<typeof startParamSchema>;

export const parseStartParam = (raw: string | null): StartParam | null => {
  const parsed = startParamSchema.safeParse(raw);

  return parsed.success ? parsed.data : null;
};
