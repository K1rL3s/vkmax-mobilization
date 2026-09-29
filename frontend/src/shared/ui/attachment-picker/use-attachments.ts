import { useState } from "react";
import { useUnmount } from "@siberiacancode/reactuse";

import { errorMessage } from "@/shared/api/errors";
import { authParams, fetchClient } from "@/shared/api/instance";

import { checkVideo } from "./check-video";

export const ATTACHMENT_LIMIT = 5;

type Attachment = {
  name: string;
  preview: string;
  isVideo: boolean;
};

export const useAttachments = () => {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isUploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revoke = (attachment: Attachment) =>
    URL.revokeObjectURL(attachment.preview);

  useUnmount(() => attachments.forEach(revoke));

  const upload = async (file: File): Promise<Attachment | string> => {
    const response = await fetchClient
      .POST("/api/files", {
        params: authParams(),
        body: { file: file as unknown as string },
        bodySerializer: (body) => {
          const form = new FormData();
          form.append("file", body.file as unknown as File);

          return form;
        },
      })
      .catch(() => undefined);

    return response?.data
      ? {
          name: response.data.name,
          preview: URL.createObjectURL(file),
          isVideo: response.data.is_video,
        }
      : errorMessage(
          response?.error,
          "Вложение не загрузилось, попробуйте ещё раз",
        );
  };

  const add = async (files: File[]) => {
    if (isUploading) return;
    setUploading(true);
    setError(null);

    const room = ATTACHMENT_LIMIT - attachments.length;
    const uploaded: (Attachment | string)[] = [];
    let videos = attachments.filter((attachment) => attachment.isVideo).length;
    for (const file of files.slice(0, room)) {
      try {
        await checkVideo(file, videos);
        const result = await upload(file);
        uploaded.push(result);
        if (typeof result !== "string" && result.isVideo) videos++;
      } catch (error) {
        uploaded.push(
          error instanceof Error ? error.message : "Не удалось прочитать файл",
        );
      }
    }

    setAttachments((current) => [
      ...current,
      ...uploaded.filter((attachment) => typeof attachment !== "string"),
    ]);
    setError(
      uploaded.find((attachment) => typeof attachment === "string") ?? null,
    );
    setUploading(false);
  };

  const remove = (name: string) => {
    setAttachments((current) => {
      current.filter((attachment) => attachment.name === name).forEach(revoke);

      return current.filter((attachment) => attachment.name !== name);
    });
  };

  return {
    attachments,
    add: (files: File[]) => void add(files),
    remove,
    isUploading,
    error,
    isFull: attachments.length >= ATTACHMENT_LIMIT,
    names: attachments.map((attachment) => attachment.name),
  };
};
