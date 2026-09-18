import { useParams } from "react-router-dom";
import type { ZodType } from "zod";

/**
 * Параметры маршрута приходят строками и могут быть какими угодно: любой
 * адрес открывается руками. Схема проверяет их на входе, дальше по коду едет
 * разобранное значение нужного типа, а не строка.
 */
export const useRouteParams = <T>(schema: ZodType<T>): T | null => {
  const params = useParams();

  return schema.safeParse(params).data ?? null;
};
