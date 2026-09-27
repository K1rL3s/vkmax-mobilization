import { useState } from "react";
import { useUnmount } from "@siberiacancode/reactuse";

import { errorMessage } from "@/shared/api/errors";
import { authParams, fetchClient } from "@/shared/api/instance";

import type { MeterType, TariffZone } from "../domain/reading";

export const PHOTO_LIMIT = 3;

type Photo = {
  name: string;
  preview: string;
};

export const useReadingPhotos = (meterType: MeterType | undefined) => {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [recognized, setRecognized] = useState<Partial<
    Record<TariffZone, number>
  > | null>(null);
  const [isUploading, setUploading] = useState(false);
  const [isRecognizing, setRecognizing] = useState(false);
  const [isUnrecognized, setUnrecognized] = useState(false);
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

  const recognize = async (name: string, type: MeterType) => {
    setRecognizing(true);
    setUnrecognized(false);

    try {
      const { data } = await fetchClient.POST(
        "/api/meters/readings/recognize",
        {
          params: authParams(),
          body: { photo_path: name, meter_type: type },
        },
      );

      setRecognized(data?.values ?? null);
      setUnrecognized(!data?.values);
    } catch {
      setUnrecognized(true);
    } finally {
      setRecognizing(false);
    }
  };

  const add = async (files: File[]) => {
    setUploading(true);
    setError(null);

    const room = PHOTO_LIMIT - photos.length;
    const uploaded = await Promise.all(files.slice(0, room).map(upload));
    const added = uploaded.filter((photo) => typeof photo !== "string");

    setPhotos((current) => [...current, ...added]);
    setError(uploaded.find((photo) => typeof photo === "string") ?? null);
    setUploading(false);

    const first = added.at(0);

    if (first && photos.length === 0 && meterType) {
      await recognize(first.name, meterType);
    }
  };

  const reset = () => {
    setPhotos((current) => {
      current.forEach(revoke);

      return [];
    });
    setRecognized(null);
    setUnrecognized(false);
    setError(null);
  };

  return {
    photos,
    add: (files: File[]) => void add(files),
    remove: (name: string) => {
      setPhotos((current) => {
        current.filter((photo) => photo.name === name).forEach(revoke);

        return current.filter((photo) => photo.name !== name);
      });
    },
    reset,
    recognized,
    isUploading,
    isRecognizing,
    isUnrecognized,
    error,
    isFull: photos.length >= PHOTO_LIMIT,
    names: photos.map((photo) => photo.name),
  };
};
