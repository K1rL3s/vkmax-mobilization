import {
  isFinished,
  isOnReview,
  type RequestListItem,
} from "@/features/request";
import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

const urgency = (item: RequestListItem) => [
  isOnReview(item.status) ? 0 : 1,
  item.deadline_at ? new Date(item.deadline_at).getTime() : Infinity,
];

export const useActiveRequest = () => {
  const requests = rqClient.useQuery("get", "/api/requests", {
    params: { ...houseParams(), query: { limit: 100 } },
  });

  return (requests.data?.items ?? [])
    .filter((item) => !isFinished(item.status))
    .sort((a, b) => {
      const [aStatus, aDeadline] = urgency(a);
      const [bStatus, bDeadline] = urgency(b);

      return aStatus - bStatus || aDeadline - bDeadline;
    })
    .at(0);
};
