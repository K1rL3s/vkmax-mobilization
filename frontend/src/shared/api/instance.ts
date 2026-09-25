import type { ApiPaths } from "./schema";
import { getMaxLaunch } from "@/shared/lib/max";
import createFetchClient from "openapi-fetch";
import createReactQueryClient from "openapi-react-query";

export const fetchClient = createFetchClient<ApiPaths>({
  baseUrl: import.meta.env.VITE_API_URL,
});

export const rqClient = createReactQueryClient(fetchClient);

export const authParams = () => ({
  header: {
    WebAppData: getMaxLaunch().initData ?? (import.meta.env.DEV ? "dev" : ""),
  },
});
