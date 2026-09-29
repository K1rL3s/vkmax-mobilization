import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

import { canProposeInitiative } from "../domain/poll";

const usePolls = () => {
  const { currentResidency: residency } = useSession();
  const isConnected = residency?.is_connected === true;

  const polls = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/polls",
    {
      params: {
        ...authParams(),
        path: { house_id: residency?.house_id ?? 0 },
      },
    },
    { enabled: isConnected },
  );

  return { residency, isConnected, polls };
};

export const usePollList = () => {
  const { residency, isConnected, polls } = usePolls();

  const items = polls.data ?? [];

  return {
    isConnected,
    isChairman: residency?.is_chairman === true,
    canPropose: canProposeInitiative(residency),
    isPending: polls.isPending,
    isError: polls.isError,
    loadError: polls.error,
    retry: () => void polls.refetch(),
    isEmpty: items.length === 0,
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

export const useNextPoll = () => {
  const { polls } = usePolls();

  return (
    (polls.data ?? [])
      .filter((poll) => poll.status === "active" && !poll.voted)
      .sort((left, right) => left.ends_at.localeCompare(right.ends_at))
      .at(0) ?? null
  );
};
