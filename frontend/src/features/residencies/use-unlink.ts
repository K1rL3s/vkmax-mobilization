import { useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import {
  forgetResidency,
  useSession,
  type Residency,
} from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

export const useUnlink = () => {
  const navigate = useNavigate();
  const { residencies, currentResidency } = useSession();
  const confirm = useConfirm<Residency>();
  const target = confirm.target;

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

        confirm.dismiss();
        await queryClient.invalidateQueries();
      },
    },
  );

  return {
    target,
    isOpen: confirm.isOpen,
    ask: (residency: Residency) => {
      unlink.reset();
      confirm.ask(residency);
    },
    cancel: () => {
      unlink.reset();
      confirm.dismiss();
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
