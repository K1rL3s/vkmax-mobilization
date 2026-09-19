import { isFinished, type RequestListItem } from "@/features/request";
import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

// тот же запрос, что у ленты: параметры совпадают, поэтому react-query отдаёт
// Главной уже загруженный список, а не ходит в сеть второй раз
const PAGE_LIMIT = 100;

// на Главной место одной заявки - той, которая ждёт жителя: сначала приёмка,
// дальше ближайший нормативный срок, так что просроченная оказывается сверху
const urgency = (item: RequestListItem) => [
  item.status === "on_review" ? 0 : 1,
  item.deadline_at ? new Date(item.deadline_at).getTime() : Infinity,
];

export const useActiveRequest = () => {
  const requests = rqClient.useQuery("get", "/api/requests", {
    params: { ...houseParams(), query: { limit: PAGE_LIMIT } },
  });

  const active = (requests.data?.items ?? [])
    .filter((item) => !isFinished(item.status))
    .sort((a, b) => {
      const [aStatus, aDeadline] = urgency(a);
      const [bStatus, bDeadline] = urgency(b);

      return aStatus - bStatus || aDeadline - bDeadline;
    });

  return active.at(0) ?? null;
};
