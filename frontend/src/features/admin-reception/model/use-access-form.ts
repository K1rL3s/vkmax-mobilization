import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { plural } from "@/shared/lib/format";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import {
  accessFormConstraints as limits,
  generateWindows,
  type AccessFlat,
} from "../domain/access-form";
import { dayKey } from "../domain/day";

const accessSchema = z
  .object({
    houseId: z.number().int().positive("Выберите дом сбора"),
    reason: z
      .string()
      .trim()
      .min(1, "Напишите, зачем нужен доступ в квартиру")
      .max(
        limits.reasonMax,
        `Сократите причину до ${limits.reasonMax} символов`,
      ),
    date: z
      .string()
      .min(1, "Выберите день сбора")
      .refine((date) => date >= dayKey(new Date()), "День доступа уже прошёл"),
    timeFrom: z.string().min(1),
    timeTo: z.string().min(1),
    windowMinutes: z
      .number()
      .int()
      .min(limits.windowMinutesMin, `Окно от ${limits.windowMinutesMin} минут`)
      .max(limits.windowMinutesMax, `Окно до ${limits.windowMinutesMax} минут`),
    perWindow: z
      .number()
      .int()
      .min(
        limits.perWindowMin,
        "В окно должна помещаться хотя бы одна квартира",
      )
      .max(limits.perWindowMax, `В окно до ${limits.perWindowMax} квартир`),
    flats: z
      .array(z.object({ flat_id: z.number(), flat_number: z.string() }))
      .min(1, "Выберите хотя бы одну квартиру"),
  })
  .superRefine((draft, ctx) => {
    if (generateWindows(draft).length === 0) {
      ctx.addIssue({
        code: "custom",
        path: ["timeTo"],
        message: "Ни одно окно не помещается: проверьте время и длину окна",
      });
    }

    if (draft.flats.length > 0 && draft.perWindow > draft.flats.length) {
      ctx.addIssue({
        code: "custom",
        path: ["perWindow"],
        message: `Выбрано ${draft.flats.length} ${plural(draft.flats.length, ["квартира", "квартиры", "квартир"])} - в окно не поместится больше`,
      });
    }
  });

type AccessDraft = z.infer<typeof accessSchema>;

export const useAccessForm = (houseIds: number[]) => {
  const navigate = useNavigate();
  const confirm = useConfirm<AccessDraft>();

  const form = useForm<AccessDraft>({
    resolver: zodResolver(accessSchema),
    defaultValues: {
      houseId: houseIds.length === 1 ? houseIds[0] : 0,
      reason: "",
      date: dayKey(new Date()),
      timeFrom: "10:00",
      timeTo: "16:00",
      windowMinutes: 120,
      perWindow: 5,
      flats: [],
    },
  });

  const [houseId, reason, date, timeFrom, timeTo, windowMinutes, flats] =
    useWatch({
      control: form.control,
      name: [
        "houseId",
        "reason",
        "date",
        "timeFrom",
        "timeTo",
        "windowMinutes",
        "flats",
      ],
    });

  const create = rqClient.useMutation("post", "/api/admin/access-requests", {
    onSuccess: async (grid) => {
      await invalidatePaths("/api/admin/access-requests");

      const chosen = confirm.target?.flats ?? [];
      const withoutCell = grid.flats_without_residents.map(
        (flatId) =>
          chosen.find((flat) => flat.flat_id === flatId)?.flat_number ??
          String(flatId),
      );

      void navigate(
        Routes.ADMIN_ACCESS.replace(
          ":accessRequestId",
          String(grid.access_request.id),
        ),
        { replace: true, state: { withoutCell } },
      );
    },
  });

  const validate = { shouldValidate: form.formState.isSubmitted };

  return {
    register: form.register,
    control: form.control,
    errors: form.formState.errors,
    houseId,
    reason,
    flats,
    windowMinutes,
    windows: generateWindows({ date, timeFrom, timeTo, windowMinutes }),
    selectHouse: (id: number) => {
      form.setValue("houseId", id, validate);
      form.setValue("flats", [], validate);
    },
    toggleFlat: (flat: AccessFlat, checked: boolean) =>
      form.setValue(
        "flats",
        checked
          ? [...flats.filter((item) => item.flat_id !== flat.flat_id), flat]
          : flats.filter((item) => item.flat_id !== flat.flat_id),
        validate,
      ),
    submit: form.handleSubmit((draft) => {
      create.reset();
      confirm.ask(draft);
    }),
    draft: confirm.target,
    isOpen: confirm.isOpen,
    isSending: create.isPending,
    sendError:
      create.isError &&
      errorMessage(
        create.error,
        "Не получилось собрать доступ. Проверьте связь и попробуйте ещё раз",
      ),
    send: () => {
      const draft = confirm.target;

      if (!draft) {
        return;
      }

      create.mutate({
        params: orgParams(),
        body: {
          house_id: draft.houseId,
          reason: draft.reason,
          date: draft.date,
          flat_ids: draft.flats.map((flat) => flat.flat_id),
          slots: generateWindows(draft).map((startsAt) => ({
            starts_at: startsAt,
            capacity: draft.perWindow,
          })),
        },
      });
    },
    dismiss: () => {
      if (!create.isPending) {
        confirm.dismiss();
      }
    },
  };
};
