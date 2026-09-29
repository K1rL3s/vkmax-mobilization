import { useState } from "react";
import { authParams, rqClient } from "@/shared/api/instance";
import { hasWorkingOrg, useSession } from "@/shared/model/session";

export const useConsent = (onContinue: () => Promise<void>) => {
  const { session, isConsentGiven, save } = useSession();
  const [checked, setChecked] = useState(false);

  const consent = rqClient.useMutation("post", "/api/me/consent", {
    onSuccess: async (data) => {
      save(data);
      await onContinue();
    },
  });

  const start = () => {
    if (isConsentGiven) {
      void onContinue();

      return;
    }

    consent.mutate({
      params: authParams(),
      body: { version: "1.2" },
    });
  };

  return {
    checked,
    setChecked,
    start,
    isPending: consent.isPending,
    error: consent.error,
    label:
      session && hasWorkingOrg(session) && session.residencies.length === 0
        ? "Открыть кабинет УК"
        : "Добавить недвижимость",
  };
};
