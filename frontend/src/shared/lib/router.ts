import { useParams } from "react-router-dom";
import type { ZodType } from "zod";

export const useRouteParams = <T>(schema: ZodType<T>): T | null => {
  const params = useParams();

  return schema.safeParse(params).data ?? null;
};
