import type { components } from "@/shared/api/schema/generated";

import type { AnnouncementDraft } from "./use-announcement-form";

export const announcementBody = (
  draft: AnnouncementDraft,
): components["schemas"]["CreateAnnouncementRequest"] => ({
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
});
