import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import {
  forgetResidency,
  useSession,
  type Residency,
} from "@/shared/model/session";

export const useUnlink = () => {
  const navigate = useNavigate();
  const { residencies, currentResidency } = useSession();
  const [target, setTarget] = useState<Residency | null>(null);

  const unlink = rqClient.useMutation(
    "delete",
    "/api/residencies/{resident_id}",
    {
      onSuccess: async () => {
        // последний адрес уносит с собой весь кабинет: завести новый житель
        // может только в онбординге
        if (residencies.length === 1) {
          await navigate(Routes.ONBOARDING_HOUSE, { replace: true });
        }

        if (target?.resident_id === currentResidency?.resident_id) {
          forgetResidency();
        }

        setTarget(null);
        await queryClient.invalidateQueries();
      },
    },
  );

  return {
    target,
    ask: (residency: Residency) => {
      unlink.reset();
      setTarget(residency);
    },
    cancel: () => {
      unlink.reset();
      setTarget(null);
    },
    submit: () => {
      if (!target) {
        return;
      }

      unlink.mutate({
        params: { ...authParams(), path: { resident_id: target.resident_id } },
      });
    },
    isPending: unlink.isPending,
    isFailed: unlink.isError,
  };
};
