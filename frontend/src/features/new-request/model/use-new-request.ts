import { useState } from "react";
import { useDebounceValue } from "@siberiacancode/reactuse";
import {
  generatePath,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { z } from "zod";

import {
  requestCategorySchema,
  useRequestCategories,
  type RequestCategory,
} from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import type { components } from "@/shared/api/schema/generated";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { haptic, useClosingConfirmation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { houseParams, useSession } from "@/shared/model/session";

import { usePhotos } from "./use-photos";

export const DESCRIPTION_LIMIT = 1000;

const handoverSchema = z.object({
  category: z.literal("charge_dispute"),
  chargeId: z.number().int().positive(),
  service: z
    .enum([
      "cold_water",
      "hot_water",
      "electricity",
      "gas",
      "heating",
      "maintenance",
      "overhaul",
      "waste",
      "penalty",
      "recalculation",
    ] satisfies components["schemas"]["ServiceType"][])
    .optional(),
  subject: z.string().max(200).optional(),
});

export const useNewRequest = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const dispute = handoverSchema.safeParse(state).data ?? null;
  const [searchParams] = useSearchParams();
  const preset =
    requestCategorySchema.safeParse(searchParams.get("category")).data ?? null;
  const entrance = z.coerce
    .number()
    .int()
    .positive()
    .safeParse(searchParams.get("entrance") ?? undefined).data;
  const { currentResidency: residency } = useSession();
  const prefill = entrance === undefined ? "" : `Подъезд ${entrance}: `;
  const [description, setDescription] = useState(prefill);
  const [picked, setPicked] = useState<RequestCategory | null>(
    dispute?.category ?? preset,
  );
  const photos = usePhotos();
  const idempotency = useIdempotencyKey();

  useClosingConfirmation(
    description.trim() !== prefill.trim() || photos.names.length > 0,
  );

  const categories = useRequestCategories();

  const text = useDebounceValue(description.trim(), 800);
  const isClassifiable = !dispute && text.length >= 15;

  const classify = rqClient.useQuery(
    "post",
    "/api/requests/classify",
    { params: authParams(), body: { text } },
    {
      enabled: isClassifiable,
      staleTime: Infinity,
      retry: 0,
      placeholderData: (previous) => previous,
    },
  );

  const suggested = isClassifiable
    ? (categories.data?.find(
        ({ category }) => category === classify.data?.category,
      )?.category ?? null)
    : null;
  const category = picked ?? suggested;

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
    haptic.success();
    await invalidatePaths("/api/requests");
    await navigate(
      generatePath(Routes.REQUEST, { requestId: String(requestId) }),
      { replace: true },
    );
  };

  const create = rqClient.useMutation("post", "/api/requests", {
    onSuccess: (request) => openCreated(request.id),
    onError: haptic.error,
  });

  const disputeCharge = rqClient.useMutation(
    "post",
    "/api/charges/{charge_id}/dispute",
    {
      onSuccess: (response) => openCreated(response.request_id),
      onError: haptic.error,
    },
  );

  const isSubmitting =
    create.isPending ||
    create.isSuccess ||
    disputeCharge.isPending ||
    disputeCharge.isSuccess;
  const isJoining =
    isSubmitting && typeof create.variables?.body.join_group_id === "number";

  const submit = (joinGroupId: number | null = null) => {
    if (!category || isSubmitting) {
      return;
    }

    if (dispute) {
      disputeCharge.mutate({
        params: {
          header: {
            ...authParams().header,
            "Idempotency-Key": idempotency.key,
          },
          path: { charge_id: dispute.chargeId },
        },
        body: { comment: description.trim(), service: dispute.service },
      });

      return;
    }

    create.mutate({
      params: {
        header: {
          ...houseParams().header,
          "Idempotency-Key": idempotency.key,
        },
      },
      body: {
        category,
        description: description.trim(),
        flat_id: residency?.flat_id ?? null,
        photos: photos.names,
        join_group_id: joinGroupId,
        llm_suggested: suggested !== null,
        llm_accepted: suggested !== null && category === suggested,
      },
    });
  };

  const neighbours = debouncedCategory === category ? similar.data : undefined;
  const failure = create.error ?? disputeCharge.error;

  return {
    description,
    setDescription: (next: string) =>
      setDescription(next.slice(0, DESCRIPTION_LIMIT)),
    category,
    suggested,
    setCategory: setPicked,
    categories: categories.data ?? [],
    isCategoriesFailed: categories.isError,
    categoriesError: categories.error,
    retryCategories: () => void categories.refetch(),
    photos,
    neighbours,
    isDispute: dispute !== null,
    subject: dispute?.subject ?? null,
    isJoining,
    isSending: isSubmitting && !isJoining,
    error:
      failure &&
      errorMessage(
        failure,
        "Заявка не ушла. Проверьте связь и попробуйте ещё раз",
      ),
    canSubmit:
      description.trim().length > 0 && category !== null && !photos.isUploading,
    missing: missingPart(description, category, photos.isUploading),
    submit,
  };
};

const missingPart = (
  description: string,
  category: RequestCategory | null,
  isUploading: boolean,
): string | null => {
  if (description.trim().length === 0) {
    return "Опишите, что случилось";
  }

  if (category === null) {
    return "Выберите категорию";
  }

  return isUploading ? "Дождитесь загрузки фото" : null;
};
