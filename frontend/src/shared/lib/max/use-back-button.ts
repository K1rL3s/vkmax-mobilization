import { useEffect } from "react";
import { useLocation, useNavigate, type To } from "react-router-dom";
import { useLatest } from "@siberiacancode/reactuse";

import { pushBackHandler } from "./back-button";

export const useBackNavigation = (fallback: To) => {
  const navigate = useNavigate();
  const { key } = useLocation();
  const { ref: handler } = useLatest(() => {
    if (key === "default") {
      navigate(fallback, { replace: true });
      return;
    }

    navigate(-1);
  });

  useEffect(() => pushBackHandler(() => handler.current()), [handler]);
};
