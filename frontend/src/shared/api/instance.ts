import type { ApiPaths } from "./schema";
import { CONFIG } from "@/shared/model/config";
import createFetchClient from "openapi-fetch";
import createReactQueryClient from "openapi-react-query";

export const fetchClient = createFetchClient<ApiPaths>({
  baseUrl: CONFIG.API_URL,
});

export const rqClient = createReactQueryClient(fetchClient);
