import { useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Consent } from "./consent";

const OnboardingPage = () => {
  const navigate = useNavigate();

  return <Consent onContinue={() => navigate(Routes.ONBOARDING_HOUSE)} />;
};

export const Component = OnboardingPage;
