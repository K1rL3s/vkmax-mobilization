import type { ChangeEvent } from "react";
import { Icon16CloseIos, IconButton, Typography } from "@maxhub/max-ui";

import { Icon, cameraIcon } from "@/shared/ui/icon";

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
    // один и тот же файл должен выбираться повторно, поэтому input очищается
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

      {!isFull && (
        <label className={styles.Add}>
          <input
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={pick}
            disabled={isUploading}
          />
          <Icon src={cameraIcon} />
          <Typography.Text variant="label-strong">
            {isUploading ? "Грузим" : "Добавить"}
          </Typography.Text>
        </label>
      )}
    </div>
  );
};
