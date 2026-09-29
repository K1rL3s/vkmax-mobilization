import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

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

const { textMax } = announcementFormConstraints;

const announcementSchema = z.object({
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
});

export type AnnouncementDraft = z.infer<typeof announcementSchema>;

const toggled = <T>(values: T[], value: T, checked: boolean) =>
  checked
    ? [...values.filter((item) => item !== value), value]
    : values.filter((item) => item !== value);

export const useAnnouncementForm = (houses: OrgHouse[]) => {
  const navigate = useNavigate();
  const confirm = useConfirm<AnnouncementDraft>();

  const form = useForm<AnnouncementDraft>({
    resolver: zodResolver(announcementSchema),
    defaultValues: {
      text: "",
      houseIds: houses.length === 1 ? [houses[0].id] : [],
      channels: ["chat"],
      urgent: false,
    },
  });

  useClosingConfirmation(form.formState.isDirty);

  const [text, houseIds, channels, urgent] = useWatch({
    control: form.control,
    name: ["text", "houseIds", "channels", "urgent"],
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

  const validate = { shouldValidate: form.formState.isSubmitted };

  return {
    register: form.register,
    errors: form.formState.errors,
    text,
    houseIds,
    channels,
    urgent,
    isAllHouses: houses.every((house) => houseIds.includes(house.id)),
    withoutChat:
      channels.length === 1 && channels[0] === "chat"
        ? houses.filter(
            (house) => houseIds.includes(house.id) && !house.chat_bound,
          )
        : [],
    toggleAllHouses: (checked: boolean) =>
      form.setValue(
        "houseIds",
        checked ? houses.map((house) => house.id) : [],
        validate,
      ),
    toggleHouse: (id: number, checked: boolean) =>
      form.setValue("houseIds", toggled(houseIds, id, checked), validate),
    toggleChannel: (channel: Channel, checked: boolean) =>
      form.setValue("channels", toggled(channels, channel, checked), validate),
    setUrgent: (checked: boolean) => form.setValue("urgent", checked),
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
        "Не получилось отправить. Проверьте связь и попробуйте ещё раз.",
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
