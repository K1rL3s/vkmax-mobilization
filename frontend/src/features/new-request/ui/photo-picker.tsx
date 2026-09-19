import type { ChangeEvent } from "react";
import { Icon16CloseIos, IconButton, Typography } from "@maxhub/max-ui";

import { cameraIcon, Icon } from "@/shared/ui/icon";

import styles from "./photo-picker.module.css";

type PhotoPickerProps = {
  photos: { name: string; preview: string }[];
  isFull: boolean;
  isUploading: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (name: string) => void;
};

export const PhotoPicker = ({
  photos,
  isFull,
  isUploading,
  onAdd,
  onRemove,
}: PhotoPickerProps) => {
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    onAdd([...(event.target.files ?? [])]);
    // один и тот же файл должен выбираться повторно, поэтому input очищается
    event.target.value = "";
  };

  return (
    <div className={styles.Picker}>
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
          <Icon src={cameraIcon} size={20} />
          <Typography.Text variant="detail-strong">
            {isUploading ? "Грузим" : "Добавить"}
          </Typography.Text>
        </label>
      )}
    </div>
  );
};
