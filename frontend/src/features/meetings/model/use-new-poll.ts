import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useClosingConfirmation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { useSession } from "@/shared/model/session";

import {
  endOfDay,
  pollDraftSchema,
  pollFormConstraints,
  type PollDraft,
} from "../domain/poll-draft";

export const useNewPoll = () => {
  const navigate = useNavigate();
  const { currentResidency: residency } = useSession();

  const form = useForm<PollDraft>({
    resolver: zodResolver(pollDraftSchema),
    mode: "onChange",
    defaultValues: {
      title: "",
      description: "",
      endsAt: "",
      options: [{ text: "" }, { text: "" }],
    },
  });

  useClosingConfirmation(form.formState.isDirty);

  const options = useFieldArray({ control: form.control, name: "options" });

  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation("post", "/api/houses/{house_id}/polls", {
    onSuccess: async (poll) => {
      await invalidatePaths("/api/houses/{house_id}/polls");
      await navigate(
        generatePath(Routes.MEETING, { pollId: String(poll.id) }),
        { replace: true },
      );
    },
  });

  const errors = form.formState.errors;

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
        options: draft.options.map(({ text }) => text),
        ends_at: endOfDay(draft.endsAt).toISOString(),
        is_multiple: false,
      },
    });
  });

  return {
    isChairman: residency?.is_chairman === true,
    register: form.register,
    registerOption: (index: number) =>
      form.register(`options.${index}.text`, {
        onChange: () => void form.trigger("options"),
      }),
    errors,
    optionsError: errors.options?.root?.message ?? errors.options?.message,
    options: options.fields,
    addOption: () => options.append({ text: "" }),
    removeOption: (index: number) => options.remove(index),
    canAddOption: options.fields.length < pollFormConstraints.optionsMax,
    canRemoveOption: options.fields.length > pollFormConstraints.optionsMin,
    control: form.control,
    minDate: new Date().toISOString().slice(0, 10),
    isSubmitting: create.isPending,
    isFailed: create.isError,
    submit,
  };
};
