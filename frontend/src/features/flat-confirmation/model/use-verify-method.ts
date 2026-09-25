import { useState } from "react";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";

import { useAccountVerification } from "./use-account-verification";
import { useOrgRequest } from "./use-org-request";
import { useResidency } from "./use-residency";

const paramsSchema = z.object({ method: z.enum(["account", "org"]) });

export const useVerifyMethod = () => {
  const params = useRouteParams(paramsSchema);
  const navigate = useNavigate();
  const { residency, returnTo, prefilledAccountNo, reload } = useResidency();

  const [accountNo, setAccountNo] = useState(prefilledAccountNo);
  const [comment, setComment] = useState("");

  const toConfirmation = async () => {
    await reload();

    if (!residency) {
      return;
    }

    await navigate(
      generatePath(Routes.FLAT_CONFIRMATION, {
        residentId: String(residency.resident_id),
      }),
      { replace: true, state: { returnTo } },
    );
  };

  const account = useAccountVerification(residency?.flat_id, toConfirmation);
  const org = useOrgRequest(residency?.flat_id, toConfirmation);

  const method = params?.method;
  const way = method === "org" ? org : account;
  const stated = accountNo.trim();

  return {
    method,
    residency,
    accountNo,
    comment,
    setComment,
    setAccountNo: (value: string) => {
      setAccountNo(value);
      way.reset();
    },
    submit: () => way.send({ accountNo: stated, comment: comment.trim() }),
    askOrg: () => {
      if (!residency) {
        return;
      }

      void navigate(
        generatePath(Routes.FLAT_CONFIRMATION_METHOD, {
          residentId: String(residency.resident_id),
          method: "org",
        }),
        { state: { returnTo, accountNo: stated } },
      );
    },
    mismatched: way.mismatched,
    isPending: way.isPending,
    isDisabled: stated === "" || way.isPending,
    isFailed: way.isFailed,
  };
};
