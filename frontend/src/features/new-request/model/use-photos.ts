import { useState } from "react";
import { useUnmount } from "@siberiacancode/reactuse";

import { authParams, fetchClient } from "@/shared/api/instance";

// бэк примет двенадцать, но пять - предел, после которого фото перестают
// помогать диспетчеру
export const PHOTO_LIMIT = 5;

type Photo = {
  name: string;
  preview: string;
};

export const usePhotos = () => {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [isUploading, setUploading] = useState(false);
  const [isFailed, setFailed] = useState(false);

  const revoke = (photo: Photo) => URL.revokeObjectURL(photo.preview);

  useUnmount(() => photos.forEach(revoke));

  const upload = async (file: File) => {
    const { data } = await fetchClient.POST("/api/files", {
      params: authParams(),
      body: { file: file as unknown as string },
      bodySerializer: (body) => {
        const form = new FormData();
        form.append("file", body.file as unknown as File);

        return form;
      },
    });

    // превью берём у выбранного файла, а не у ответа: серверу от нас нужно
    // только имя, которое уедет в заявку
    return data && { name: data.name, preview: URL.createObjectURL(file) };
  };

  const add = async (files: File[]) => {
    setUploading(true);
    setFailed(false);

    const room = PHOTO_LIMIT - photos.length;
    const uploaded = await Promise.all(files.slice(0, room).map(upload));

    setPhotos((current) => [
      ...current,
      ...uploaded.filter((photo) => photo !== undefined),
    ]);
    setFailed(uploaded.some((photo) => photo === undefined));
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
    isFailed,
    isFull: photos.length >= PHOTO_LIMIT,
    names: photos.map((photo) => photo.name),
  };
};
