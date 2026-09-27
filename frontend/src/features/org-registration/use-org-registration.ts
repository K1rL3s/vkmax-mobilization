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
  const form = useForm<z.infer<typeof innSchema>>({
    resolver: zodResolver(innSchema),
    defaultValues: { inn: "" },
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

  const found = lookup.data?.found ? lookup.data : null;

  return {
    innField: form.register("inn", { onChange: () => lookup.reset() }),
    innError: form.formState.errors.inn?.message,
    search: form.handleSubmit(({ inn }) =>
      lookup.mutate({ params: authParams(), body: { inn } }),
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
