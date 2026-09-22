import { z } from "zod";

import { activateFlatInvite } from "@/features/flat-invite";
import { errorDetail } from "@/shared/api/errors";
import { authParams, fetchClient } from "@/shared/api/instance";
import {
  reloadSession,
  selectOrg,
  selectResidency,
  type Session,
} from "@/shared/model/session";

import type { StartParam } from "./start-param";

type HouseCommand = Extract<StartParam, { kind: "house" | "qr" }>;
type FlatCommand = Extract<StartParam, { kind: "flat" }>;
type DemoCommand = Extract<StartParam, { kind: "demo" }>;
type ExecutableCommand = Exclude<StartParam, { kind: "invite" | "register" }>;

export type DeeplinkTarget = "resident" | "admin";

export type DeeplinkExecution = {
  target: DeeplinkTarget;
};

export type DeeplinkPageState =
  | { status: "consent" }
  | { status: "bot-only"; hasResidency: boolean }
  | { status: "failure"; kind: StartParam["kind"]; hasResidency: boolean };

class ExpectedDeeplinkError extends Error {}

const residencySchema = z.object({ resident_id: z.number().int().positive() });
const demoActivationSchema = z.object({
  org: z.object({ org_id: z.number().int().positive() }),
  residency: residencySchema,
});

const attempts = new Map<
  string,
  | { status: "waiting-consent" }
  | { status: "running"; promise: Promise<DeeplinkAttempt> }
  | { status: "succeeded"; value: DeeplinkExecution }
  | { status: "failed"; error: ExpectedDeeplinkError }
  | { status: "ignored" }
>();

export type DeeplinkAttempt =
  | { status: "succeeded"; value: DeeplinkExecution }
  | { status: "failed"; error: ExpectedDeeplinkError }
  | { status: "ignored" };

export const waitForDeeplinkConsent = (raw: string) => {
  if (!attempts.has(raw)) {
    attempts.set(raw, { status: "waiting-consent" });
  }
};

export const runDeeplinkOnce = (
  raw: string,
  execute: () => Promise<DeeplinkExecution>,
): Promise<DeeplinkAttempt> => {
  const attempt = attempts.get(raw);

  if (attempt?.status === "running") {
    return attempt.promise;
  }

  if (attempt?.status === "succeeded" || attempt?.status === "failed") {
    return Promise.resolve(attempt);
  }

  if (attempt?.status === "ignored") {
    return Promise.resolve({ status: "ignored" });
  }

  const promise = execute()
    .then((value): DeeplinkAttempt => {
      const succeeded = { status: "succeeded" as const, value };
      attempts.set(raw, succeeded);

      return succeeded;
    })
    .catch((error: unknown): DeeplinkAttempt => {
      if (!(error instanceof ExpectedDeeplinkError)) {
        throw error;
      }

      const failed = { status: "failed" as const, error };
      attempts.set(raw, failed);

      return failed;
    });

  attempts.set(raw, { status: "running", promise });

  return promise;
};

export const retryDeeplink = (raw: string) => {
  if (attempts.get(raw)?.status === "failed") {
    attempts.delete(raw);
  }
};

export const ignoreDeeplink = (raw: string) => {
  attempts.set(raw, { status: "ignored" });
};

export const shouldHandleDeeplink = (raw: string): boolean =>
  attempts.get(raw)?.status !== "ignored";

const linkHouse = async (command: HouseCommand) => {
  try {
    const { data, error } = await fetchClient.POST(
      "/api/houses/{house_id}/link",
      {
        params: {
          ...authParams(),
          path: { house_id: command.houseId },
        },
        body: {
          role: "owner",
          source: command.kind === "qr" ? "qr" : "chat",
          ...(command.kind === "qr" ? { entrance: command.entrance } : {}),
        },
      },
    );

    if (error) {
      throw new ExpectedDeeplinkError("Не получилось привязать дом");
    }

    return residencySchema.parse(data);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ExpectedDeeplinkError("Нет связи с сервером");
    }

    throw error;
  }
};

export const executeHouseDeeplink = async (
  command: HouseCommand,
): Promise<DeeplinkExecution> => {
  const residency = await linkHouse(command);
  await reloadSession();
  await selectResidency(residency.resident_id);

  return { target: "resident" };
};

export const executeFlatDeeplink = async (
  command: FlatCommand,
): Promise<DeeplinkExecution> => {
  let residency;

  try {
    residency = residencySchema.parse(await activateFlatInvite(command.code));
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ExpectedDeeplinkError("Нет связи с сервером");
    }

    // activateFlatInvite бросает конверт API: 404 - кода нет, 409 - истёк,
    // отозван, исчерпан или житель уже в другой квартире
    const detail = errorDetail(error);

    if (detail === undefined) {
      throw error;
    }

    throw new ExpectedDeeplinkError(detail);
  }

  await reloadSession();
  await selectResidency(residency.resident_id);

  return { target: "resident" };
};

export const executeDemoDeeplink = async (
  command: DemoCommand,
): Promise<DeeplinkExecution> => {
  let access;

  try {
    const { data, error } = await fetchClient.POST("/api/demo/activate", {
      params: authParams(),
    });

    if (error) {
      throw new ExpectedDeeplinkError("Демо-данные пока не готовы");
    }

    access = demoActivationSchema.parse(data);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ExpectedDeeplinkError("Нет связи с сервером");
    }

    throw error;
  }

  await reloadSession();

  if (command.cabinet === "resident") {
    await selectResidency(access.residency.resident_id);

    return { target: "resident" };
  }

  await selectOrg(access.org.org_id);

  return { target: "admin" };
};

export const executeDeeplink = (
  command: ExecutableCommand,
): Promise<DeeplinkExecution> => {
  switch (command.kind) {
    case "flat":
      return executeFlatDeeplink(command);
    case "demo":
      return executeDemoDeeplink(command);
    case "house":
    case "qr":
      return executeHouseDeeplink(command);
  }
};

export const defaultRouteForSession = (session: Session): string =>
  session.residencies.length > 0 ? "/home" : "/";
