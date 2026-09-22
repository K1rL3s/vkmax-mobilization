import { useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { loadSession, startTarget } from "@/shared/model/session";
import { Consent } from "./consent";

const OnboardingPage = () => {
  const navigate = useNavigate();

  const continueAfterConsent = async () => {
    const target = startTarget(await loadSession());

    await navigate(target === "admin" ? Routes.ADMIN : Routes.ONBOARDING_HOUSE);
  };

  return <Consent onContinue={continueAfterConsent} />;
};

export const Component = OnboardingPage;
