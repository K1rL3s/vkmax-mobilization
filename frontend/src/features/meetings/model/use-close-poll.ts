import { isForbidden } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import { refreshPoll } from "./use-poll";

export const useClosePoll = (pollId: number) => {
  const confirm = useConfirm();

  const close = rqClient.useMutation("post", "/api/polls/{poll_id}/close", {
    onSuccess: async () => {
      await refreshPoll();
      confirm.dismiss();
    },
    onError: async (error) => {
      if (isForbidden(error)) {
        await invalidatePaths("/api/polls/{poll_id}");
      }
    },
  });

  return {
    isOpen: confirm.isOpen,
    ask: () => confirm.ask(),
    dismiss: () => {
      if (!close.isPending) {
        confirm.dismiss();
      }
    },
    isPending: close.isPending,
    error:
      close.isError &&
      (isForbidden(close.error)
        ? "Завершить опрос больше нельзя: права изменились."
        : "Не получилось завершить опрос. Проверьте связь и попробуйте ещё раз"),
    confirm: () =>
      close.mutate({ params: { ...authParams(), path: { poll_id: pollId } } }),
  };
};
