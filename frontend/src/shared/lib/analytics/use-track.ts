import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";

export const useTrack = () => {
  const { mutate } = rqClient.useMutation("post", "/api/events");

  return (event: components["schemas"]["TrackEventRequest"]) =>
    mutate({ params: authParams(), body: event });
};
