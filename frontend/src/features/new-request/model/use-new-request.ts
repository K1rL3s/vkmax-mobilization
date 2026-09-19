import { useState } from "react";
import { useDebounceValue } from "@siberiacancode/reactuse";
import { generatePath, useNavigate } from "react-router-dom";

import { useRequestCategories, type RequestCategory } from "@/features/request";
import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import { houseParams, useSession } from "@/shared/model/session";

import { usePhotos } from "./use-photos";

// бэк длину описания не ограничивает; тысяча знаков - предел, после которого
// диспетчер перестаёт читать
export const DESCRIPTION_LIMIT = 1000;

export const useNewRequest = () => {
  const navigate = useNavigate();
  const { currentResidency: residency } = useSession();
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<RequestCategory | null>(null);
  const photos = usePhotos();

  const categories = useRequestCategories();

  // соседей ищем с задержкой: пока житель перебирает чипы, запрос за каждый
  // тап не нужен
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
    { enabled: debouncedCategory !== null },
  );

  const create = rqClient.useMutation("post", "/api/requests", {
    onSuccess: async (request) => {
      await queryClient.invalidateQueries({
        queryKey: ["get", "/api/requests"],
      });
      // мастер уходит из истории: назад из карточки житель вернётся в ленту
      await navigate(
        generatePath(Routes.REQUEST, { requestId: String(request.id) }),
        { replace: true },
      );
    },
  });

  const submit = (joinGroupId?: number) => {
    if (!category) {
      return;
    }

    create.mutate({
      params: houseParams(),
      body: {
        category,
        description: description.trim(),
        flat_id: residency?.flat_id ?? null,
        photos: photos.names,
        join_group_id: joinGroupId ?? null,
        // подсказки категории по описанию нет: ставить флаги по своему `if`
        // значит врать аналитике УК
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
    isSubmitting: create.isPending || create.isSuccess,
    isFailed: create.isError,
    canSubmit: description.trim().length > 0 && category !== null,
    submit,
  };
};
