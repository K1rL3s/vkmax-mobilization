import { useState } from "react";
import { useDebounceValue } from "@siberiacancode/reactuse";
import { generatePath, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useRequestCategories, type RequestCategory } from "@/features/request";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import { houseParams, useSession } from "@/shared/model/session";

import { usePhotos } from "./use-photos";

export const DESCRIPTION_LIMIT = 1000;

const handoverSchema = z.object({
  category: z.literal("charge_dispute"),
  chargeId: z.number().int().positive(),
});

export const useNewRequest = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const dispute = handoverSchema.safeParse(state).data ?? null;
  const { currentResidency: residency } = useSession();
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<RequestCategory | null>(
    dispute?.category ?? null,
  );
  const photos = usePhotos();

  const categories = useRequestCategories();

  const debouncedCategory = useDebounceValue(category, 400);

  const similar = rqClient.useQuery(
    "get",
    "/api/requests/similar",
    {
      params: {
        ...houseParams(),
        query: { category: debouncedCategory ?? "other" },
      },
    },
    { enabled: debouncedCategory !== null && !dispute },
  );

  const openCreated = async (requestId: number) => {
    await invalidatePaths("/api/requests");
    await navigate(
      generatePath(Routes.REQUEST, { requestId: String(requestId) }),
      { replace: true },
    );
  };

  const create = rqClient.useMutation("post", "/api/requests", {
    onSuccess: (request) => openCreated(request.id),
  });

  const disputeCharge = rqClient.useMutation(
    "post",
    "/api/charges/{charge_id}/dispute",
    { onSuccess: (response) => openCreated(response.request_id) },
  );

  const submit = (joinGroupId: number | null = null) => {
    if (!category) {
      return;
    }

    if (dispute) {
      disputeCharge.mutate({
        params: { ...authParams(), path: { charge_id: dispute.chargeId } },
        body: { comment: description.trim() },
      });

      return;
    }

    create.mutate({
      params: houseParams(),
      body: {
        category,
        description: description.trim(),
        flat_id: residency?.flat_id ?? null,
        photos: photos.names,
        join_group_id: joinGroupId,
        llm_suggested: false,
        llm_accepted: false,
      },
    });
  };

  const neighbours = debouncedCategory === category ? similar.data : undefined;

  return {
    description,
    setDescription: (next: string) =>
      setDescription(next.slice(0, DESCRIPTION_LIMIT)),
    category,
    setCategory,
    categories: categories.data ?? [],
    isCategoriesFailed: categories.isError,
    photos,
    neighbours,
    isDispute: dispute !== null,
    isSubmitting:
      create.isPending ||
      create.isSuccess ||
      disputeCharge.isPending ||
      disputeCharge.isSuccess,
    isFailed: create.isError || disputeCharge.isError,
    canSubmit: description.trim().length > 0 && category !== null,
    submit,
  };
};
