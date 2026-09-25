import { authParams, fetchClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { selectResidency } from "@/shared/model/session";

export const activateFlatInvite = async (code: string) => {
  const { data, error } = await fetchClient.POST(
    "/api/flat-invites/{code}/activate",
    { params: { ...authParams(), path: { code } } },
  );

  if (error) {
    throw error;
  }

  await selectResidency(data.resident_id);
  await queryClient.refetchQueries({ queryKey: ["get", "/api/me"] });

  return data;
};
