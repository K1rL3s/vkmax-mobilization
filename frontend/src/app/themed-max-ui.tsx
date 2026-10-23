import type { ReactNode } from "react";
import { MaxUI } from "@maxhub/max-ui";

import { useTheme } from "@/shared/model/session";

export const ThemedMaxUI = ({ children }: { children: ReactNode }) => {
  const theme = useTheme();

  return (
    <MaxUI resetBody colorScheme={theme === "system" ? undefined : theme}>
      {children}
    </MaxUI>
  );
};
