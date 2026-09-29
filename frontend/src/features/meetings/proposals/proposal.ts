import { z } from "zod";

import type { components } from "@/shared/api/schema/generated";
import { formatDay } from "@/shared/lib/format";
import type { StatusPillTone } from "@/shared/ui/status-pill";

export type Proposal = components["schemas"]["ProposalItem"];

export const proposalFormConstraints = {
  text: 1000,
  textMin: 10,
  answer: 1000,
};

export const proposalDraftSchema = z.object({
  text: z
    .string()
    .trim()
    .min(
      proposalFormConstraints.textMin,
      `Опишите предложение подробнее: не меньше ${proposalFormConstraints.textMin} символов`,
    )
    .max(
      proposalFormConstraints.text,
      `Предложение длиннее ${proposalFormConstraints.text} символов`,
    ),
});

export type ProposalDraft = z.infer<typeof proposalDraftSchema>;

export const declineDraftSchema = z.object({
  answer: z
    .string()
    .trim()
    .min(1, "Объясните автору, почему предложение отклонено")
    .max(
      proposalFormConstraints.answer,
      `Ответ длиннее ${proposalFormConstraints.answer} символов`,
    ),
});

export type DeclineDraft = z.infer<typeof declineDraftSchema>;

export const statusLabel = (status: Proposal["status"]) => {
  if (status === "accepted") {
    return "Принято";
  }

  return status === "declined" ? "Отклонено" : "Новое";
};

export const statusTone = (status: Proposal["status"]): StatusPillTone => {
  if (status === "accepted") {
    return "positive";
  }

  return status === "declined" ? "negative" : "themed";
};

export const proposalDate = (proposal: Proposal) =>
  `Отправлено ${formatDay(proposal.created_at)}`;

const carriedSchema = z.object({
  proposalId: z.number().int().positive(),
  text: z.string(),
});

export const carriedProposal = (state: unknown) =>
  carriedSchema.safeParse(state).data ?? null;
