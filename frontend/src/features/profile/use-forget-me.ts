import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import { forgetResidency } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

export const useForgetMe = () => {
  const navigate = useNavigate();
  const confirm = useConfirm();

  const forget = rqClient.useMutation("delete", "/api/me", {
    onSuccess: async () => {
      forgetResidency();
      queryClient.clear();
      await navigate(Routes.WELCOME, { replace: true });
    },
  });

  return {
    isOpen: confirm.isOpen,
    ask: () => {
      forget.reset();
      confirm.ask();
    },
    cancel: () => {
      forget.reset();
      confirm.dismiss();
    },
    submit: () => forget.mutate({ params: authParams() }),
    isPending: forget.isPending,
    error:
      forget.isError &&
      errorMessage(
        forget.error,
        "Не получилось удалить данные. Проверьте связь и попробуйте ещё раз",
      ),
  };
};
