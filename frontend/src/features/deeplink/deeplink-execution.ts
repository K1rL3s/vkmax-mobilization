import { matchPath } from "react-router-dom";

import { activateFlatInvite } from "@/features/flat-invite";
import { errorDetail } from "@/shared/api/errors";
import { authParams, fetchClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import {
  hasWorkingOrg,
  reloadSession,
  selectCabinet,
  selectOrg,
  selectResidency,
  startTarget,
  workingOrgs,
  type Session,
} from "@/shared/model/session";

import type { StartParam } from "./start-param";

type DeeplinkExecution = { target: "resident" | "admin" };

type DeeplinkAttempt =
  | { status: "succeeded"; value: DeeplinkExecution }
  | { status: "failed"; error: unknown }
  | { status: "ignored" };

export type DeeplinkPageState =
  | { status: "consent" }
  | { status: "bot-only"; hasResidency: boolean }
  | { status: "no-access"; route: string }
  | {
      status: "failure";
      kind: StartParam["kind"];
      hasResidency: boolean;
      error: unknown;
    };

class ExpectedDeeplinkError extends Error {}

const attempts = new Map<
  string,
  { status: "running"; promise: Promise<DeeplinkAttempt> } | DeeplinkAttempt
>();

export const runDeeplinkOnce = (
  raw: string,
  execute: () => Promise<DeeplinkExecution>,
): Promise<DeeplinkAttempt> => {
  const attempt = attempts.get(raw);

  if (attempt?.status === "running") {
    return attempt.promise;
  }

  if (attempt) {
    return Promise.resolve(attempt);
  }

  const promise = execute()
    .then(
      (value): DeeplinkAttempt => ({ status: "succeeded", value }),
      (error: unknown): DeeplinkAttempt => {
        if (!(error instanceof ExpectedDeeplinkError)) {
          throw error;
        }

        return { status: "failed", error: error.cause };
      },
    )
    .then((settled) => {
      attempts.set(raw, settled);

      return settled;
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

const expectedFailure = (error: unknown): never => {
  throw error instanceof TypeError || errorDetail(error) !== undefined
    ? new ExpectedDeeplinkError(undefined, { cause: error })
    : error;
};

const residencyIn = async (houseId: number) =>
  (await reloadSession()).residencies.find(
    (residency) => residency.house_id === houseId,
  );

const executeHouseDeeplink = async (
  command: Extract<StartParam, { kind: "house" | "qr" | "obj" }>,
): Promise<DeeplinkExecution> => {
  const existing =
    command.kind === "obj" ||
    (command.kind === "house" && command.category !== null)
      ? await residencyIn(command.houseId)
      : undefined;

  if (existing) {
    await selectResidency(existing.resident_id);

    return { target: "resident" };
  }

  const { data, error } = await fetchClient
    .POST("/api/houses/{house_id}/link", {
      params: { ...authParams(), path: { house_id: command.houseId } },
      body: {
        role: "owner",
        source: command.kind === "house" ? "chat" : "qr",
        ...(command.kind === "house" ? {} : { entrance: command.entrance }),
      },
    })
    .catch(expectedFailure);

  if (error) {
    throw new ExpectedDeeplinkError(undefined, { cause: error });
  }

  await reloadSession();
  await selectResidency(data.resident_id);

  return { target: "resident" };
};

const executeFlatDeeplink = async (
  command: Extract<StartParam, { kind: "flat" }>,
): Promise<DeeplinkExecution> => {
  const residency = await activateFlatInvite(command.code).catch(
    expectedFailure,
  );

  await reloadSession();
  await selectResidency(residency.resident_id);

  return { target: "resident" };
};

const executeDemoDeeplink = async (
  command: Extract<StartParam, { kind: "demo" }>,
): Promise<DeeplinkExecution> => {
  const { data, error } = await fetchClient
    .POST("/api/demo/activate", {
      params: authParams(),
      body: { number: command.profile, admin: command.cabinet === "admin" },
    })
    .catch(expectedFailure);

  if (error) {
    throw new ExpectedDeeplinkError(undefined, { cause: error });
  }

  await reloadSession();

  if (command.cabinet === "resident") {
    await selectResidency(data.residency.resident_id);
    selectCabinet("resident");

    return { target: "resident" };
  }

  await selectOrg(data.org.org_id);
  selectCabinet("admin");

  return { target: "admin" };
};

export const executeDeeplink = (
  command: Exclude<StartParam, { kind: "invite" | "register" | "path" }>,
): Promise<DeeplinkExecution> => {
  switch (command.kind) {
    case "flat":
      return executeFlatDeeplink(command);
    case "demo":
      return executeDemoDeeplink(command);
    case "house":
    case "qr":
    case "obj":
      return executeHouseDeeplink(command);
  }
};

export const defaultRouteForSession = (session: Session): string => {
  switch (startTarget(session)) {
    case "admin":
      return Routes.ADMIN;
    case "home":
      return Routes.HOME;
    case "onboarding":
      return Routes.WELCOME;
  }
};

const orgOfRequest = async (session: Session, requestId: number) => {
  for (const org of workingOrgs(session)) {
    const { data } = await fetchClient
      .GET("/api/admin/requests/{request_id}", {
        params: {
          header: { ...authParams().header, "X-Org-Id": org.org_id },
          path: { request_id: requestId },
        },
      })
      .catch(() => ({ data: undefined }));

    if (data) {
      return org.org_id;
    }
  }

  return null;
};

export const openPathDeeplink = async (
  path: string,
  session: Session,
): Promise<string | null> => {
  if (!path.startsWith(Routes.ADMIN)) {
    return path;
  }

  if (!hasWorkingOrg(session)) {
    return null;
  }

  const requestId = Number(
    matchPath(Routes.ADMIN_REQUEST, path)?.params.requestId,
  );

  if (Number.isSafeInteger(requestId)) {
    const orgId = await orgOfRequest(session, requestId);

    if (orgId === null) {
      return null;
    }

    await selectOrg(orgId);
  }

  selectCabinet("admin");

  return path;
};
