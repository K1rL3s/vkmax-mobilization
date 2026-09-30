import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { Routes } from "@/shared/model/routes";
import { loadSession, startTarget } from "@/shared/model/session";
import { Consent } from "./consent";

const OnboardingPage = () => {
  const navigate = useNavigate();
  const isForgotten = z
    .object({ forgotten: z.literal(true) })
    .safeParse(useLocation().state).success;

  const continueAfterConsent = async () => {
    const target = startTarget(await loadSession());

    await navigate(target === "admin" ? Routes.ADMIN : Routes.ONBOARDING_HOUSE);
  };

  return (
    <Consent
      notice={isForgotten ? "Ваши данные удалены" : undefined}
      onContinue={continueAfterConsent}
    />
  );
};

export const Component = OnboardingPage;
