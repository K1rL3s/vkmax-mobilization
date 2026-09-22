import { authParams, fetchClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { selectResidency } from "@/shared/model/session";

/**
 * Впускает в квартиру по коду собственника и делает её текущей. Бросает
 * конверт API, вызывающий показывает `error.error.detail`: 404 - кода нет,
 * 409 - код истёк, отозван, исчерпан или житель привязан к другой квартире,
 * 403 - нет согласия на обработку данных
 */
export const activateFlatInvite = async (code: string) => {
  const { data, error } = await fetchClient.POST(
    "/api/flat-invites/{code}/activate",
    { params: { ...authParams(), path: { code } } },
  );

  if (error) {
    throw error;
  }

  await selectResidency(data.resident_id);
  // invalidate обновляет только активные запросы, а из лоадера на /api/me
  // никто не подписан; ключ session.ts не экспортирует, префикс совпадает с
  // ключом openapi-react-query при любых параметрах
  await queryClient.refetchQueries({ queryKey: ["get", "/api/me"] });

  return data;
};
