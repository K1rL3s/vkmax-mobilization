import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { pushBackHandler } from "./back-button";

export const useBackNavigation = (active = true) => {
  const navigate = useNavigate();
  const { key } = useLocation();

  useEffect(
    () => (active ? pushBackHandler(() => void navigate(-1)) : undefined),
    [active, navigate, key],
  );
};
