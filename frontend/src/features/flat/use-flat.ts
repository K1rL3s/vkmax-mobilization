import { residencyState } from "@/features/flat-confirmation";
import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

export const useFlat = () => {
  const { currentResidency: residency } = useSession();
  const flatId = residency?.flat_id ?? null;

  const card = rqClient.useQuery(
    "get",
    "/api/flats/{flat_id}",
    { params: { ...authParams(), path: { flat_id: flatId ?? 0 } } },
    { enabled: flatId !== null },
  );

  if (!residency) {
    return { residency: null };
  }

  const state = residencyState(residency);

  return {
    residency,
    card,
    state,
    canConfirm: state === "ways" || state === "pending" || state === "rejected",
  };
};
