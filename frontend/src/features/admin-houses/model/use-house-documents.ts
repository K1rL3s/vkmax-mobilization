import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import { houseDocumentFormConstraints } from "../domain/house-document";

type HouseDocument = components["schemas"]["HouseDocumentItem"];

const { titleMax } = houseDocumentFormConstraints;

const documentSchema = z.object({
  title: z
    .string()
    .trim()
    .max(titleMax, `Сократите название до ${titleMax} символов`),
});

type DocumentDraft = z.infer<typeof documentSchema>;

export const useHouseDocuments = (houseId: number) => {
  const form = useForm<DocumentDraft>({
    resolver: zodResolver(documentSchema),
    mode: "onChange",
    defaultValues: { title: "" },
  });
  const removal = useConfirm<HouseDocument>();
  const refresh = () =>
    invalidatePaths("/api/admin/houses/{house_id}/documents");

  const documents = rqClient.useQuery(
    "get",
    "/api/admin/houses/{house_id}/documents",
    { params: { ...orgParams(), path: { house_id: houseId } } },
  );
  const upload = rqClient.useMutation("post", "/api/admin/files");
  const create = rqClient.useMutation(
    "post",
    "/api/admin/houses/{house_id}/documents",
    {
      onSuccess: async () => {
        form.reset();
        await refresh();
      },
    },
  );
  const remove = rqClient.useMutation(
    "delete",
    "/api/admin/houses/{house_id}/documents/{document_id}",
    {
      onSuccess: async () => {
        removal.dismiss();
        await refresh();
      },
    },
  );

  const add = (file: File) =>
    form.handleSubmit(async ({ title }) => {
      upload.reset();
      create.reset();
      const { name } = await upload.mutateAsync({
        params: orgParams(),
        body: { file: file as unknown as string },
        bodySerializer: (body) => {
          const payload = new FormData();
          payload.append("file", body.file as unknown as File);

          return payload;
        },
      });
      await create.mutateAsync({
        params: { ...orgParams(), path: { house_id: houseId } },
        body: {
          name,
          title: title || file.name.replace(/\.pdf$/i, "").slice(0, titleMax),
        },
      });
    })();

  const addFailure = upload.error ?? create.error;

  return {
    items: documents.data ?? [],
    isPending: documents.isPending,
    isError: documents.isError,
    loadError: documents.error,
    retry: () => void documents.refetch(),
    registerTitle: () => form.register("title"),
    titleError: form.formState.errors.title?.message,
    isAdding: upload.isPending || create.isPending,
    addError:
      addFailure &&
      errorMessage(addFailure, "Документ не загрузился, попробуйте ещё раз"),
    add: (file: File) => void add(file).catch(() => undefined),
    removal,
    isRemoving: remove.isPending,
    removeError:
      remove.isError &&
      errorMessage(remove.error, "Не получилось удалить. Попробуйте ещё раз"),
    askRemove: (document: HouseDocument) => {
      remove.reset();
      removal.ask(document);
    },
    confirmRemove: () =>
      removal.target &&
      remove.mutate({
        params: {
          ...orgParams(),
          path: { house_id: houseId, document_id: removal.target.id },
        },
      }),
  };
};
