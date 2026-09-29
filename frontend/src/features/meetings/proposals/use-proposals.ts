import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { haptic } from "@/shared/lib/max";
import { useSession } from "@/shared/model/session";

import {
  declineDraftSchema,
  proposalDraftSchema,
  type DeclineDraft,
  type Proposal,
  type ProposalDraft,
} from "./proposal";

const refreshProposals = () =>
  invalidatePaths(
    "/api/houses/{house_id}/proposals",
    "/api/houses/{house_id}/proposals/my",
  );

export const useProposals = () => {
  const { currentResidency: residency } = useSession();
  const isChairman = residency?.is_chairman === true;
  const isConnected = residency?.is_connected === true;
  const params = {
    ...authParams(),
    path: { house_id: residency?.house_id ?? 0 },
  };

  const mine = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/proposals/my",
    { params },
    { enabled: isConnected && !isChairman },
  );

  const incoming = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/proposals",
    { params },
    { enabled: isConnected && isChairman },
  );

  const form = useForm<ProposalDraft>({
    resolver: zodResolver(proposalDraftSchema),
    mode: "onChange",
    defaultValues: { text: "" },
  });

  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation(
    "post",
    "/api/houses/{house_id}/proposals",
    {
      onSuccess: async () => {
        haptic.success();
        idempotency.renew();
        form.reset();
        await refreshProposals();
      },
      onError: haptic.error,
    },
  );

  const send = form.handleSubmit((draft) =>
    create.mutate({
      params: {
        header: {
          ...authParams().header,
          "Idempotency-Key": idempotency.key,
        },
        path: params.path,
      },
      body: { text: draft.text },
    }),
  );

  return {
    isVisible: isConnected,
    isChairman,
    hasChairman: mine.data?.has_chairman === true,
    mine: mine.data?.items ?? [],
    incoming: incoming.data ?? [],
    isPending: isChairman ? incoming.isPending : mine.isPending,
    loadError: incoming.error ?? mine.error,
    register: form.register,
    errors: form.formState.errors,
    control: form.control,
    isSending: create.isPending,
    sendError: create.error,
    send,
  };
};

export const useAnswerProposal = () => {
  const [declining, setDeclining] = useState<Proposal | null>(null);

  const form = useForm<DeclineDraft>({
    resolver: zodResolver(declineDraftSchema),
    mode: "onChange",
    defaultValues: { answer: "" },
  });

  const answer = rqClient.useMutation(
    "post",
    "/api/proposals/{proposal_id}/answer",
    {
      onSuccess: async () => {
        haptic.success();
        setDeclining(null);
        form.reset();
        await refreshProposals();
      },
      onError: haptic.error,
    },
  );

  const respond = (
    proposal: Proposal,
    body: {
      accepted: boolean;
      answer?: string | null;
      poll_id?: number | null;
    },
  ) =>
    answer.mutate({
      params: { ...authParams(), path: { proposal_id: proposal.id } },
      body,
    });

  return {
    declining,
    ask: (proposal: Proposal) => {
      form.reset();
      setDeclining(proposal);
    },
    dismiss: () => setDeclining(null),
    register: form.register,
    errors: form.formState.errors,
    accept: (proposal: Proposal) => respond(proposal, { accepted: true }),
    decline: form.handleSubmit((draft) => {
      if (declining !== null) {
        respond(declining, { accepted: false, answer: draft.answer });
      }
    }),
    isPending: answer.isPending,
    error: answer.error,
  };
};

export const useCarryProposalToPoll = () => {
  const carry = rqClient.useMutation(
    "post",
    "/api/proposals/{proposal_id}/answer",
    { onSuccess: refreshProposals },
  );

  return (proposalId: number, pollId: number) =>
    carry.mutate({
      params: { ...authParams(), path: { proposal_id: proposalId } },
      body: { accepted: true, poll_id: pollId },
    });
};
