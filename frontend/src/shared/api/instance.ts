import type { ApiPaths } from "./schema";
import { getInitData } from "@/shared/lib/max";
import { CONFIG } from "@/shared/model/config";
import createFetchClient from "openapi-fetch";
import createReactQueryClient from "openapi-react-query";

export const fetchClient = createFetchClient<ApiPaths>({
  baseUrl: CONFIG.API_URL,
});

export const rqClient = createReactQueryClient(fetchClient);

// заголовок объявлен обязательным у каждой ручки контракта, поэтому он
// подставляется параметрами запроса, а не middleware: забытая авторизация
// должна быть ошибкой типов, а не сюрпризом в рантайме. Вне MAX данных запуска
// нет, и в dev-сборке уходит заглушка - иначе с моком не поработать
export const authParams = () => ({
  header: { WebAppData: getInitData() ?? (import.meta.env.DEV ? "dev" : "") },
});
