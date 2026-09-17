import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { MaxUI as UIProvider } from "@maxhub/max-ui";
import { queryClient } from "@/shared/api/query-client";

export const Providers = ({ children }: PropsWithChildren) => {
  return (
    <UIProvider resetBody>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </UIProvider>
  );
};
