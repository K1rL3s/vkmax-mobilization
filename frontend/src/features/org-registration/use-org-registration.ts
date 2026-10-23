import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import {
  reloadSession,
  selectCabinet,
  selectOrg,
} from "@/shared/model/session";

export const INN_LIMIT = 12;

const innSchema = z.object({
  inn: z
    .string()
    .trim()
    .regex(/^(\d{10}|\d{12})$/, "ИНН - это 10 или 12 цифр"),
});

export const useOrgRegistration = (code: string) => {
  const navigate = useNavigate();
  const invited = rqClient.useQuery(
    "post",
    "/api/orgs/lookup",
    { params: authParams(), body: { deeplink_code: code } },
    { retry: false, staleTime: Infinity },
  );
  const preset = invited.data?.found ? invited.data : null;
  const form = useForm<z.infer<typeof innSchema>>({
    resolver: zodResolver(innSchema),
    defaultValues: { inn: "" },
    values: preset?.inn ? { inn: preset.inn } : undefined,
  });

  const lookup = rqClient.useMutation("post", "/api/orgs/lookup");

  const register = rqClient.useMutation("post", "/api/orgs", {
    onSuccess: async (org) => {
      await reloadSession();
      await selectOrg(org.id);
      selectCabinet("admin");
      await navigate(Routes.ADMIN_REQUESTS, { replace: true });
    },
  });

  const shownOrg = () => {
    if (lookup.data?.found) {
      return lookup.data;
    }
    if (lookup.isIdle && !form.formState.isDirty) {
      return preset;
    }
    return null;
  };
  const found = shownOrg();

  return {
    innField: form.register("inn", { onChange: () => lookup.reset() }),
    innError: form.formState.errors.inn?.message,
    search: form.handleSubmit(({ inn }) =>
      lookup.mutate({
        params: authParams(),
        body: { inn, deeplink_code: code },
      }),
    ),
    isSearching: lookup.isPending,
    searchError:
      lookup.error &&
      errorMessage(
        lookup.error,
        "Не получилось проверить ИНН. Проверьте связь и попробуйте ещё раз",
      ),
    isNotFound: lookup.data?.found === false,
    found,
    register: () => {
      if (!found?.inn || !found.name || !found.phone || !found.address) {
        return;
      }

      register.mutate({
        params: authParams(),
        body: {
          deeplink_code: code,
          inn: found.inn,
          license_no: found.license_no ?? null,
          name: found.name,
          phone: found.phone,
          address: found.address,
        },
      });
    },
    isRegistering: register.isPending || register.isSuccess,
    registerError:
      register.error &&
      errorMessage(
        register.error,
        "Не получилось зарегистрировать. Проверьте связь и попробуйте ещё раз",
      ),
  };
};
