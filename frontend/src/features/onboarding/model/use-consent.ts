import { useState } from "react";
import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

export const useConsent = (onContinue: () => Promise<void>) => {
  const { isConsentGiven, save } = useSession();
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
      body: { version: "1.0" },
    });
  };

  return {
    checked: isConsentGiven || checked,
    accepted: isConsentGiven,
    setChecked,
    start,
    isPending: consent.isPending,
    isError: consent.isError,
  };
};
