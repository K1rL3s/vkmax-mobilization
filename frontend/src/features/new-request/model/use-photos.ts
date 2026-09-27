import { useState } from "react";
import { useUnmount } from "@siberiacancode/reactuse";

import { errorMessage } from "@/shared/api/errors";
import { authParams, fetchClient } from "@/shared/api/instance";

export const PHOTO_LIMIT = 5;

type Photo = {
  name: string;
  preview: string;
};

export const usePhotos = () => {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [isUploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revoke = (photo: Photo) => URL.revokeObjectURL(photo.preview);

  useUnmount(() => photos.forEach(revoke));

  const upload = async (file: File): Promise<Photo | string> => {
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
      ? { name: response.data.name, preview: URL.createObjectURL(file) }
      : errorMessage(
          response?.error,
          "Фото не загрузилось, попробуйте ещё раз",
        );
  };

  const add = async (files: File[]) => {
    setUploading(true);
    setError(null);

    const room = PHOTO_LIMIT - photos.length;
    const uploaded = await Promise.all(files.slice(0, room).map(upload));

    setPhotos((current) => [
      ...current,
      ...uploaded.filter((photo) => typeof photo !== "string"),
    ]);
    setError(uploaded.find((photo) => typeof photo === "string") ?? null);
    setUploading(false);
  };

  const remove = (name: string) => {
    setPhotos((current) => {
      current.filter((photo) => photo.name === name).forEach(revoke);

      return current.filter((photo) => photo.name !== name);
    });
  };

  return {
    photos,
    add: (files: File[]) => void add(files),
    remove,
    isUploading,
    error,
    isFull: photos.length >= PHOTO_LIMIT,
    names: photos.map((photo) => photo.name),
  };
};
