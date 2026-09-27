import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});

export const invalidatePaths = (...paths: string[]) =>
  Promise.all(
    paths.map((path) =>
      queryClient.invalidateQueries({ queryKey: ["get", path] }),
    ),
  );
