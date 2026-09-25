import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient();

export const invalidatePaths = (...paths: string[]) =>
  Promise.all(
    paths.map((path) =>
      queryClient.invalidateQueries({ queryKey: ["get", path] }),
    ),
  );
