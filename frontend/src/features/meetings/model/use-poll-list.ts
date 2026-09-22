import { useQuery } from "@tanstack/react-query";

import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

// один запрос на вкладку и на карточку Главной: ключ тот же, react-query
// отдаёт второму потребителю кеш
const usePolls = () => {
  const { currentResidency: residency } = useSession();
  const isConnected = residency?.is_connected === true;

  const polls = useQuery({
    ...rqClient.queryOptions("get", "/api/houses/{house_id}/polls", {
      params: {
        ...authParams(),
        path: { house_id: residency?.house_id ?? 0 },
      },
    }),
    enabled: isConnected,
  });

  return { residency, isConnected, polls };
};

export const usePollList = () => {
  const { residency, isConnected, polls } = usePolls();

  const items = polls.data ?? [];

  return {
    isConnected,
    isChairman: residency?.is_chairman === true,
    isPending: polls.isPending,
    isError: polls.isError,
    retry: () => void polls.refetch(),
    isEmpty: items.length === 0,
    // порядок внутри разделов - серверный: активные свежие сверху
    sections: [
      {
        title: "Идут",
        items: items.filter((poll) => poll.status === "active"),
      },
      {
        title: "Завершённые",
        items: items.filter((poll) => poll.status === "closed"),
      },
    ].filter((section) => section.items.length > 0),
  };
};

// на Главной живёт то, что ждёт действия: ближайший по сроку идущий опрос,
// в котором житель ещё не голосовал. Проголосовал во всех - карточки нет
export const useNextPoll = () => {
  const { polls } = usePolls();

  return (
    [...(polls.data ?? [])]
      .filter((poll) => poll.status === "active" && !poll.voted)
      .sort((left, right) => left.ends_at.localeCompare(right.ends_at))
      .at(0) ?? null
  );
};
