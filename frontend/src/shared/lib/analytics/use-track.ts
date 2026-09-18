import { useCallback } from "react";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";

export type TrackEvent = components["schemas"]["TrackEventRequest"];

export const useTrack = () => {
  const { mutate } = rqClient.useMutation("post", "/api/events");

  return useCallback(
    (event: TrackEvent) => mutate({ params: authParams(), body: event }),
    [mutate],
  );
};
