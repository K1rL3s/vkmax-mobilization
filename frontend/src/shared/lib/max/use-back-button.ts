import { useEffect, useRef } from "react";
import { useLocation, useNavigate, type To } from "react-router-dom";

import { pushBackHandler } from "./back-button";

export interface UseBackButtonOptions {
  enabled?: boolean;
}

export const useBackButton = (
  onClick: () => void,
  { enabled = true }: UseBackButtonOptions = {},
) => {
  const handler = useRef(onClick);

  useEffect(() => {
    handler.current = onClick;
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }

    return pushBackHandler(() => handler.current());
  }, [enabled]);
};

export const useBackNavigation = (
  fallback?: To,
  options?: UseBackButtonOptions,
) => {
  const navigate = useNavigate();
  const { key } = useLocation();

  useBackButton(() => {
    if (fallback !== undefined && key === "default") {
      navigate(fallback, { replace: true });
      return;
    }

    navigate(-1);
  }, options);
};
