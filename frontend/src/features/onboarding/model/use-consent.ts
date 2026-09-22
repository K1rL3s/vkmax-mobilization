import { useState } from "react";
import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

export const CONSENT_VERSION = "1.0";

export const useConsent = (onContinue: () => void | Promise<void>) => {
  const { isConsentGiven, save } = useSession();
  const [checked, setChecked] = useState(false);

  const accepted = isConsentGiven;

  const consent = rqClient.useMutation("post", "/api/me/consent", {
    onSuccess: async (data) => {
      save(data);
      await onContinue();
    },
  });

  const start = () => {
    if (accepted) {
      void onContinue();

      return;
    }

    consent.mutate({
      params: authParams(),
      body: { version: CONSENT_VERSION },
    });
  };

  return {
    // согласие уже дано - галочка остаётся стоять, чтобы экран не дёргался
    checked: accepted || checked,
    accepted,
    setChecked,
    start,
    isPending: consent.isPending,
    isError: consent.isError,
  };
};
