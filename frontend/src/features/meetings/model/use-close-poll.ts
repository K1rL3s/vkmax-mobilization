import { isForbidden } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { useConfirm } from "@/shared/ui/confirm-dialog";

export const useClosePoll = (pollId: number) => {
  const confirm = useConfirm();

  const close = rqClient.useMutation("post", "/api/polls/{poll_id}/close", {
    onSuccess: async () => {
      await Promise.all(
        [
          "/api/polls/{poll_id}",
          "/api/polls/{poll_id}/results",
          "/api/houses/{house_id}/polls",
        ].map((path) =>
          queryClient.invalidateQueries({ queryKey: ["get", path] }),
        ),
      );
      confirm.dismiss();
    },
    onError: async (error) => {
      // права могли измениться, пока экран открыт: перечитанная карточка
      // придёт без can_manage и уберёт кнопку вместе с диалогом
      if (isForbidden(error)) {
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/polls/{poll_id}"],
        });
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
    // права могли измениться, пока экран был открыт
    error:
      close.isError &&
      (isForbidden(close.error)
        ? "Завершить опрос больше нельзя: права изменились."
        : "Не получилось завершить опрос. Проверьте связь и попробуйте ещё раз."),
    confirm: () => {
      if (!close.isPending) {
        close.mutate({
          params: { ...authParams(), path: { poll_id: pollId } },
        });
      }
    },
  };
};
