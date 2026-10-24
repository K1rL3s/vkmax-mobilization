import { isClientError } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { plural } from "@/shared/lib/format";
import { orgParams } from "@/shared/model/session";

import { addressees, channelsLabel, scopeLabel } from "../domain/labels";

import { announcementBody } from "./announcement-body";
import type { AnnouncementDraft } from "./use-announcement-form";
import type { OrgHouse } from "./use-announcements";

type Preview = components["schemas"]["AnnouncementPreviewResponse"];

const recipientsLine = (draft: AnnouncementDraft, preview: Preview) => {
  const parts = [
    draft.channels.includes("chat") && `чатов домов ${preview.chats_count}`,
    draft.channels.includes("direct") && `жителей ${preview.residents_count}`,
  ].filter(Boolean);

  return `Адресатов: ${preview.recipients_count} - ${parts.join(", ")}`;
};

const unreachableLine = (preview: Preview) => {
  const stopped = preview.bot_stopped_count;
  const muted = preview.muted_count;

  if (stopped + muted === 0) {
    return undefined;
  }

  const parts = [
    stopped > 0 &&
      `${stopped} ${plural(stopped, ["остановил", "остановили", "остановили"])} бота`,
    muted > 0 &&
      `${muted} ${plural(muted, ["выключил", "выключили", "выключили"])} объявления`,
  ].filter(Boolean);

  return `Не получат сразу: ${stopped + muted} - ${parts.join(", ")}`;
};

const withoutChatLine = (
  draft: AnnouncementDraft,
  preview: Preview,
  houses: OrgHouse[],
) => {
  const withoutChat = preview.houses_without_chat;

  if (draft.channels.includes("direct") || withoutChat.length === 0) {
    return undefined;
  }

  if (withoutChat.length === draft.houseIds.length) {
    return "Ни у одного из этих домов нет привязанного чата, объявление никто не получит";
  }

  const addresses = withoutChat.map(
    (id) => houses.find((house) => house.id === id)?.address ?? `дом ${id}`,
  );

  return `Не получат дома без чата: ${addresses.join("; ")}`;
};

export const useAnnouncementReview = (
  draft: AnnouncementDraft,
  houses: OrgHouse[],
) => {
  const preview = rqClient.useQuery(
    "post",
    "/api/admin/announcements/preview",
    { params: orgParams(), body: announcementBody(draft) },
    { retry: (count, error) => !isClientError(error) && count < 1 },
  );
  const scope = scopeLabel({
    entrances: draft.scope === "entrances" ? draft.entrances : null,
    flats_count: draft.scope === "flats" ? draft.flats.length : null,
  });
  const data = preview.data;

  return {
    title: draft.urgent
      ? "Проверьте срочное объявление"
      : "Проверьте объявление",
    summary: `${[addressees(draft.houseIds, houses), scope].filter(Boolean).join(", ")}. ${channelsLabel(draft.channels)}`,
    isReady: preview.isSuccess,
    isLoading: preview.isPending,
    error: preview.error,
    retry: () => void preview.refetch(),
    message: data?.message,
    hashtagNote:
      data?.chat_hashtag && `В чате дома в конце будет ${data.chat_hashtag}`,
    lines: data
      ? [
          recipientsLine(draft, data),
          unreachableLine(data),
          withoutChatLine(draft, data, houses),
          data.is_demo &&
            data.residents_count > 0 &&
            "Демо: личное сообщение придёт только вам",
        ].filter((line) => typeof line === "string")
      : [],
  };
};
