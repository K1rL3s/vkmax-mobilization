import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useClosingConfirmation } from "@/shared/lib/max";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";

import { canProposeInitiative } from "../domain/poll";
import {
  initiativeDraftSchema,
  type InitiativeDraft,
} from "../domain/poll-draft";

export const useNewInitiative = () => {
  const navigate = useNavigate();
  const { currentResidency: residency } = useSession();

  const form = useForm<InitiativeDraft>({
    resolver: zodResolver(initiativeDraftSchema),
    mode: "onChange",
    defaultValues: { title: "", description: "" },
  });

  useClosingConfirmation(form.formState.isDirty);

  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation(
    "post",
    "/api/houses/{house_id}/initiatives",
    {
      onSuccess: async (poll) => {
        await invalidatePaths("/api/houses/{house_id}/polls");
        await navigate(
          generatePath(Routes.MEETING, { pollId: String(poll.id) }),
          { replace: true },
        );
      },
    },
  );

  const submit = form.handleSubmit((draft) => {
    if (residency === undefined) {
      return;
    }

    create.mutate({
      params: {
        header: {
          ...authParams().header,
          "Idempotency-Key": idempotency.key,
        },
        path: { house_id: residency.house_id },
      },
      body: {
        title: draft.title,
        description: draft.description.trim() || null,
      },
    });
  });

  return {
    canPropose: canProposeInitiative(residency),
    register: form.register,
    errors: form.formState.errors,
    control: form.control,
    isSubmitting: create.isPending,
    error: create.error,
    submit,
  };
};
