import type { HouseCard } from "@/features/house";
import { authParams, rqClient } from "@/shared/api/instance";
import { getWebApp, haptic } from "@/shared/lib/max";

export const useChatJoin = (house: HouseCard, updatedAt: number) => {
  const join = rqClient.useMutation(
    "post",
    "/api/houses/{house_id}/chat/join",
    { onSuccess: () => haptic.success(), onError: haptic.error },
  );
  const chat = house.chat_join;

  if (!chat) {
    return null;
  }

  if (!chat.joined) {
    return {
      kind: "join" as const,
      title: chat.title,
      waiting: join.isSuccess && join.submittedAt > updatedAt,
      pending: join.isPending,
      error: join.error,
      request: () =>
        join.mutate({
          params: { ...authParams(), path: { house_id: house.id } },
        }),
    };
  }

  const { link } = chat;

  return link && getWebApp()?.openLink
    ? {
        kind: "open" as const,
        title: chat.title,
        open: () => getWebApp()?.openLink?.(link),
      }
    : null;
};
