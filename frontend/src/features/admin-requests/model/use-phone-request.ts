import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  useRequestCategories,
  type RequestCategory,
  type RequestPlace,
} from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { useClosingConfirmation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { orgParams } from "@/shared/model/session";

import { requestFormConstraints } from "../domain/request-form-constraints";
import { isCategory } from "../domain/request-workflow";
import { refreshRequests } from "./refresh-requests";
import {
  useRequestFlats,
  useRequestHouses,
  useRequestResidents,
} from "./use-request-search";

const phoneSchema = z
  .object({
    houseId: z.number().int().positive("Выберите дом"),
    category: z.custom<RequestCategory>(isCategory, "Выберите категорию"),
    description: z
      .string()
      .trim()
      .min(1, "Опишите проблему")
      .max(requestFormConstraints.description, "Сократите описание"),
    flatId: z.number().int().nonnegative(),
    residentId: z.number().int().nonnegative(),
    callerName: z
      .string()
      .trim()
      .max(requestFormConstraints.callerName, "Сократите имя"),
    callerPhone: z
      .string()
      .trim()
      .max(requestFormConstraints.callerPhone, "Сократите телефон"),
    place: z.enum(["flat", "house"] satisfies RequestPlace[]).nullable(),
  })
  .superRefine((draft, context) => {
    if (draft.residentId || draft.flatId) return;
    if (!draft.callerName)
      context.addIssue({
        code: "custom",
        path: ["callerName"],
        message: "Укажите имя звонившего",
      });
    if (!draft.callerPhone)
      context.addIssue({
        code: "custom",
        path: ["callerPhone"],
        message: "Без квартиры или жителя нужен телефон звонившего",
      });
  });

export const usePhoneRequest = () => {
  const navigate = useNavigate();
  const houses = useRequestHouses();
  const categories = useRequestCategories();
  const form = useForm<z.infer<typeof phoneSchema>>({
    resolver: zodResolver(phoneSchema),
    defaultValues: {
      houseId: 0,
      category: undefined,
      description: "",
      flatId: 0,
      residentId: 0,
      callerName: "",
      callerPhone: "",
      place: null,
    },
  });
  useClosingConfirmation(form.formState.isDirty);
  const [houseId, flatId, category, place] = useWatch({
    control: form.control,
    name: ["houseId", "flatId", "category", "place"],
  });
  const asksPlace =
    categories.data?.some(
      (item) => item.category === category && !item.place,
    ) ?? false;
  const flats = useRequestFlats(houseId);
  const residents = useRequestResidents(houseId, flatId);
  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation("post", "/api/admin/requests/phone", {
    onSuccess: async (request) => {
      await refreshRequests();
      await navigate(
        generatePath(Routes.ADMIN_REQUEST, { requestId: String(request.id) }),
        { replace: true },
      );
    },
  });

  const changeHouse = (value: string) => {
    houses.change(value);
    flats.reset();
    residents.reset();
    form.setValue("houseId", 0);
    form.setValue("flatId", 0);
    form.setValue("residentId", 0);
  };
  const selectHouse = (id: number | string) => {
    const house = houses.select(id);
    if (house) form.setValue("houseId", house.id, { shouldValidate: true });
  };
  const changeFlat = (value: string) => {
    flats.change(value);
    residents.reset();
    form.setValue("flatId", 0);
    form.setValue("residentId", 0);
  };
  const selectFlat = (id: number | string) => {
    const flat = flats.select(id);
    if (flat) form.setValue("flatId", flat.id, { shouldValidate: true });
  };
  const changeResident = (value: string) => {
    residents.change(value);
    form.setValue("residentId", 0);
  };
  const selectResident = (id: number | string) => {
    const resident = residents.select(id);
    if (resident)
      form.setValue("residentId", resident.resident_id, {
        shouldValidate: true,
      });
  };
  const isPlaceMissing = () => {
    const missing = asksPlace && !form.getValues("place");
    if (missing) form.setError("place", { message: "Укажите, где проблема" });
    return missing;
  };
  const submit = form.handleSubmit((draft) => {
    if (create.isPending || create.isSuccess) return;
    const residentFlat = residents.selected?.flat_id;
    if (draft.residentId && draft.flatId && residentFlat !== draft.flatId) {
      form.setError("residentId", {
        message: "Выберите жителя этого дома и квартиры",
      });
      return;
    }
    if (isPlaceMissing()) return;
    create.mutate({
      params: {
        header: {
          ...orgParams().header,
          "Idempotency-Key": idempotency.key,
        },
      },
      body: {
        house_id: draft.houseId,
        category: draft.category,
        description: draft.description,
        flat_id: draft.flatId || null,
        resident_id: draft.residentId || null,
        caller_name: draft.callerName || null,
        caller_phone: draft.callerPhone || null,
        place: asksPlace ? draft.place : null,
      },
    });
  }, isPlaceMissing);

  return {
    form,
    category,
    selectCategory: (value: RequestCategory) =>
      form.setValue("category", value, { shouldValidate: true }),
    hasHouse: houseId > 0,
    houseSearch: { ...houses, change: changeHouse, select: selectHouse },
    flatSearch: { ...flats, change: changeFlat, select: selectFlat },
    residentSearch: {
      ...residents,
      change: changeResident,
      select: selectResident,
    },
    categories: categories.data ?? [],
    isPending: categories.isPending,
    isError: categories.isLoadingError,
    loadError: categories.error,
    isSubmitting: create.isPending || create.isSuccess,
    error: create.isError
      ? errorMessage(
          create.error,
          "Не удалось создать заявку. Проверьте связь и попробуйте ещё раз",
        )
      : null,
    retry: () => void categories.refetch(),
    submit,
    asksPlace,
    place,
    selectPlace: (value: RequestPlace) =>
      form.setValue("place", value, { shouldValidate: true }),
  };
};
