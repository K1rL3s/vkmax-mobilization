import type { ChangeEvent } from "react";
import { Icon16CloseIos, IconButton, Typography } from "@maxhub/max-ui";

import { Icon, cameraIcon, plusIcon } from "@/shared/ui/icon";

import styles from "./photo-strip.module.css";

type PhotoStripProps = {
  photos: { name: string; preview: string }[];
  isFull: boolean;
  isUploading: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (name: string) => void;
};

export const PhotoStrip = ({
  photos,
  isFull,
  isUploading,
  onAdd,
  onRemove,
}: PhotoStripProps) => {
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    onAdd([...(event.target.files ?? [])]);
    event.target.value = "";
  };

  return (
    <div className={styles.Strip}>
      {photos.map((photo) => (
        <div key={photo.name} className={styles.Thumb}>
          <img src={photo.preview} alt="" />
          <IconButton
            className={styles.Remove}
            variant="overlay"
            size="small"
            aria-label="Убрать фото"
            onClick={() => onRemove(photo.name)}
          >
            <Icon16CloseIos />
          </IconButton>
        </div>
      ))}

      {isUploading && (
        <div className={styles.Add}>
          <Icon src={cameraIcon} />
          <Typography.Text variant="label-strong">Грузим</Typography.Text>
        </div>
      )}

      {!isUploading &&
        !isFull &&
        [
          { label: "Снять", icon: cameraIcon, capture: "environment" as const },
          { label: "Из галереи", icon: plusIcon, capture: undefined },
        ].map((source) => (
          <label key={source.label} className={styles.Add}>
            <input
              type="file"
              accept="image/*"
              capture={source.capture}
              multiple
              hidden
              onChange={pick}
            />
            <Icon src={source.icon} />
            <Typography.Text variant="label-strong">
              {source.label}
            </Typography.Text>
          </label>
        ))}
    </div>
  );
};
