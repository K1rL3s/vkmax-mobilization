import { useState } from "react";

import { errorDetail, errorMessage, isConflict } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { orgParams } from "@/shared/model/session";

import type { Resident, ResidentActionKind } from "../domain/resident";

type Step = "menu" | Exclude<ResidentActionKind, "unblock">;

const refresh = () =>
  invalidatePaths(
    "/api/admin/houses/{house_id}/residents",
    "/api/admin/houses/{house_id}",
  );

const actionError = (error: unknown) =>
  isConflict(error)
    ? (errorDetail(error) ?? "Житель уже изменился, список перечитан")
    : errorMessage(
        error,
        "Не получилось. Проверьте связь и попробуйте ещё раз",
      );

export const useResidentActions = () => {
  const [state, setState] = useState<{ resident: Resident; step: Step }>();

  const options = {
    onSuccess: async () => {
      setState(undefined);
      await refresh();
    },
    onError: async (error: unknown) => {
      if (isConflict(error)) {
        await refresh();
      }
    },
  };

  const block = rqClient.useMutation(
    "post",
    "/api/admin/residents/{resident_id}/block",
    options,
  );
  const unblock = rqClient.useMutation(
    "post",
    "/api/admin/residents/{resident_id}/unblock",
    options,
  );
  const revoke = rqClient.useMutation(
    "post",
    "/api/admin/residents/{resident_id}/revoke-verification",
    options,
  );
  const chairman = rqClient.useMutation(
    "post",
    "/api/admin/residents/{resident_id}/chairman",
    options,
  );

  const all = [block, unblock, revoke, chairman];
  const isPending = all.some((mutation) => mutation.isPending);
  const failed = all.find((mutation) => mutation.isError);

  const params = () => ({
    ...orgParams(),
    path: { resident_id: state?.resident.resident_id ?? 0 },
  });

  return {
    resident: state?.resident ?? null,
    step: state?.step ?? null,
    isPending,
    error: failed ? actionError(failed.error) : null,
    open: (resident: Resident) => {
      all.forEach((mutation) => mutation.reset());
      setState({ resident, step: "menu" });
    },
    close: () => {
      if (!isPending) {
        setState(undefined);
      }
    },
    choose: (kind: ResidentActionKind) => {
      if (!state) {
        return;
      }

      all.forEach((mutation) => mutation.reset());

      if (kind === "unblock") {
        unblock.mutate({ params: params() });
      } else {
        setState({ ...state, step: kind });
      }
    },
    submitReason: (reason: string) => {
      if (state?.step === "block") {
        block.mutate({ params: params(), body: { reason } });
      }

      if (state?.step === "revoke") {
        revoke.mutate({ params: params(), body: { reason } });
      }
    },
    confirmChairman: () =>
      chairman.mutate({
        params: params(),
        body: { is_chairman: state?.step === "chairman" },
      }),
  };
};
