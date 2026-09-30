import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import type { AccessFlat } from "@/features/admin-reception";
import { requestCategorySchema } from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useClosingConfirmation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import { announcementFormConstraints } from "../domain/announcement-form-constraints";
import type { Channel } from "../domain/labels";

import type { OrgHouse, SentOutcome } from "./use-announcements";

const { textMax, documentsMax, documentTitleMax } = announcementFormConstraints;

const pad = (value: number) => String(value).padStart(2, "0");

const localStamp = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;

const announcementSchema = z
  .object({
    text: z
      .string()
      .trim()
      .min(1, "Напишите текст объявления")
      .max(textMax, `Сократите объявление до ${textMax} символов`),
    houseIds: z.array(z.number()).min(1, "Выберите хотя бы один дом"),
    channels: z
      .array(z.enum(["chat", "direct"]))
      .min(1, "Выберите хотя бы один канал"),
    urgent: z.boolean(),
    scope: z.enum(["house", "entrances", "flats"]),
    entrances: z.array(z.number()),
    flats: z.array(z.object({ flat_id: z.number(), flat_number: z.string() })),
    works: z.boolean(),
    worksCategory: requestCategorySchema.nullable(),
    worksFromDay: z.string(),
    worksFromTime: z.string(),
    worksToDay: z.string(),
    worksToTime: z.string(),
    documents: z
      .array(
        z.object({
          name: z.string(),
          title: z
            .string()
            .trim()
            .min(1, "Назовите документ")
            .max(
              documentTitleMax,
              `Сократите название до ${documentTitleMax} символов`,
            ),
        }),
      )
      .max(documentsMax),
  })
  .superRefine((draft, ctx) => {
    if (!draft.works) {
      return;
    }

    const from = `${draft.worksFromDay}T${draft.worksFromTime}`;
    const to = `${draft.worksToDay}T${draft.worksToTime}`;
    const message = () => {
      if (!draft.worksFromDay || !draft.worksFromTime) {
        return "Укажите, когда начнутся работы";
      }

      if (!draft.worksToDay || !draft.worksToTime) {
        return "Укажите, когда закончатся работы";
      }

      if (to <= from) {
        return "Работы должны закончиться позже, чем начнутся";
      }

      return to <= localStamp(new Date()) ? "Срок работ уже прошёл" : null;
    };
    const error = message();

    if (error) {
      ctx.addIssue({ code: "custom", path: ["worksToDay"], message: error });
    }
  })
  .refine(
    (draft) => draft.scope !== "entrances" || draft.entrances.length > 0,
    { message: "Выберите хотя бы один подъезд", path: ["entrances"] },
  )
  .refine((draft) => draft.scope !== "flats" || draft.flats.length > 0, {
    message: "Выберите хотя бы одну квартиру",
    path: ["flats"],
  });

export type AnnouncementDraft = z.infer<typeof announcementSchema>;

export type AnnouncementFormModel = ReturnType<typeof useAnnouncementForm>;

type Scope = AnnouncementDraft["scope"];

const toggled = <T>(values: T[], value: T, checked: boolean) =>
  checked
    ? [...values.filter((item) => item !== value), value]
    : values.filter((item) => item !== value);

export const useAnnouncementForm = (houses: OrgHouse[]) => {
  const navigate = useNavigate();
  const confirm = useConfirm<AnnouncementDraft>();

  const today = localStamp(new Date()).slice(0, 10);
  const form = useForm<AnnouncementDraft>({
    resolver: zodResolver(announcementSchema),
    defaultValues: {
      text: "",
      houseIds: houses.length === 1 ? [houses[0].id] : [],
      channels: ["chat"],
      urgent: false,
      scope: "house",
      entrances: [],
      flats: [],
      works: false,
      worksCategory: null,
      worksFromDay: today,
      worksFromTime: "10:00",
      worksToDay: today,
      worksToTime: "18:00",
      documents: [],
    },
  });
  const documents = useFieldArray({ control: form.control, name: "documents" });

  useClosingConfirmation(form.formState.isDirty);

  const [
    text,
    houseIds,
    channels,
    urgent,
    scope,
    entrances,
    flats,
    works,
    worksCategory,
  ] = useWatch({
    control: form.control,
    name: [
      "text",
      "houseIds",
      "channels",
      "urgent",
      "scope",
      "entrances",
      "flats",
      "works",
      "worksCategory",
    ],
  });

  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation("post", "/api/admin/announcements", {
    onSuccess: async (created) => {
      await invalidatePaths("/api/admin/announcements");

      const withoutChat = (created.houses_without_chat ?? []).map(
        (id) => houses.find((house) => house.id === id)?.address ?? `дом ${id}`,
      );

      void navigate(Routes.ADMIN_ANNOUNCEMENTS, {
        replace: true,
        state: {
          sent: {
            recipients: created.recipients_count,
            withoutChat,
          } satisfies SentOutcome,
        },
      });
    },
  });

  const upload = rqClient.useMutation("post", "/api/admin/files");

  const validate = { shouldValidate: form.formState.isSubmitted };

  const setHouseIds = (ids: number[]) => {
    form.setValue("scope", "house");
    form.setValue("entrances", []);
    form.setValue("flats", []);
    form.setValue("houseIds", ids, validate);
  };

  return {
    register: form.register,
    control: form.control,
    errors: form.formState.errors,
    text,
    houseIds,
    channels,
    urgent,
    scope,
    entrances,
    flats,
    scopeHouse:
      houseIds.length === 1
        ? houses.find((house) => house.id === houseIds[0])
        : undefined,
    isAllHouses: houses.every((house) => houseIds.includes(house.id)),
    withoutChat:
      channels.length === 1 && channels[0] === "chat"
        ? houses.filter(
            (house) => houseIds.includes(house.id) && !house.chat_bound,
          )
        : [],
    toggleAllHouses: (checked: boolean) =>
      setHouseIds(checked ? houses.map((house) => house.id) : []),
    toggleHouse: (id: number, checked: boolean) =>
      setHouseIds(toggled(houseIds, id, checked)),
    setScope: (next: Scope) => {
      form.setValue("scope", next, validate);

      if (next !== "house") {
        form.setValue(
          "channels",
          next === "flats" ? ["direct"] : toggled(channels, "direct", true),
          validate,
        );
      }
    },
    toggleEntrance: (entrance: number, checked: boolean) =>
      form.setValue(
        "entrances",
        toggled(entrances, entrance, checked).sort((a, b) => a - b),
        validate,
      ),
    toggleFlat: (flat: AccessFlat, checked: boolean) =>
      form.setValue(
        "flats",
        checked
          ? [...flats.filter((item) => item.flat_id !== flat.flat_id), flat]
          : flats.filter((item) => item.flat_id !== flat.flat_id),
        validate,
      ),
    toggleChannel: (channel: Channel, checked: boolean) =>
      form.setValue("channels", toggled(channels, channel, checked), validate),
    setUrgent: (checked: boolean) => form.setValue("urgent", checked),
    works,
    worksCategory,
    setWorksCategory: (category: AnnouncementDraft["worksCategory"]) =>
      form.setValue("worksCategory", category),
    documents: documents.fields,
    removeDocument: documents.remove,
    isUploading: upload.isPending,
    uploadError:
      upload.isError &&
      errorMessage(upload.error, "Документ не загрузился, попробуйте ещё раз"),
    addDocument: (file: File) => {
      upload.mutate(
        {
          params: orgParams(),
          body: { file: file as unknown as string },
          bodySerializer: (body) => {
            const payload = new FormData();
            payload.append("file", body.file as unknown as File);

            return payload;
          },
        },
        {
          onSuccess: ({ name }) =>
            documents.append({
              name,
              title: file.name
                .replace(/\.pdf$/i, "")
                .slice(0, documentTitleMax),
            }),
        },
      );
    },
    submit: form.handleSubmit((draft) => {
      create.reset();
      confirm.ask(draft);
    }),
    draft: confirm.target,
    isSending: create.isPending,
    sendError:
      create.isError &&
      errorMessage(
        create.error,
        "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
      ),
    send: () => {
      const draft = confirm.target;

      if (!draft) {
        return;
      }

      create.mutate({
        params: {
          header: {
            ...orgParams().header,
            "Idempotency-Key": idempotency.key,
          },
        },
        body: {
          text: draft.text,
          house_ids: draft.houseIds,
          channels: draft.channels,
          urgent: draft.urgent,
          entrances: draft.scope === "entrances" ? draft.entrances : undefined,
          flat_ids:
            draft.scope === "flats"
              ? draft.flats.map((flat) => flat.flat_id)
              : undefined,
          works: draft.works
            ? {
                category: draft.worksCategory,
                starts_at: `${draft.worksFromDay}T${draft.worksFromTime}`,
                ends_at: `${draft.worksToDay}T${draft.worksToTime}`,
              }
            : undefined,
          documents: draft.works
            ? draft.documents.map(({ name, title }) => ({ name, title }))
            : [],
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
