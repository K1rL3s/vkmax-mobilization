import { useState } from "react";
import { useUnmount } from "@siberiacancode/reactuse";

import { authParams, fetchClient } from "@/shared/api/instance";

import type { MeterType, TariffZone } from "../domain/reading";

// фото обязательно, иначе бэк показание не примет; трёх кадров хватает на
// табло с любым числом зон
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

    // превью берём у выбранного файла: серверу от нас нужно только имя, оно же
    // уедет в показание и в распознавание
    return data && { name: data.name, preview: URL.createObjectURL(file) };
  };

  const recognize = async (name: string, type: MeterType) => {
    setRecognizing(true);

    const { data } = await fetchClient.POST("/api/meters/readings/recognize", {
      params: authParams(),
      body: { photo_path: name, meter_type: type },
    });

    // распознаванию разрешено не получиться: житель просто вводит цифры сам
    setRecognized(data?.values ?? null);
    setRecognizing(false);
  };

  const add = async (files: File[]) => {
    setUploading(true);
    setFailed(false);

    const room = PHOTO_LIMIT - photos.length;
    const uploaded = await Promise.all(files.slice(0, room).map(upload));
    const added = uploaded.filter((photo) => photo !== undefined);

    setPhotos((current) => [...current, ...added]);
    setFailed(uploaded.some((photo) => photo === undefined));
    setUploading(false);

    const first = added.at(0);

    // распознаём первый кадр табло: следующие фото житель добавляет как
    // доказательство, и переписывать ими уже проверенные значения незачем
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
    setFailed(false);
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
    isFailed,
    isFull: photos.length >= PHOTO_LIMIT,
    names: photos.map((photo) => photo.name),
  };
};
