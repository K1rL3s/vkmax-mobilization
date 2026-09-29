import type { ChangeEvent } from "react";
import { Icon16CloseIos, IconButton, Typography } from "@maxhub/max-ui";

import { cameraIcon, Icon } from "@/shared/ui/icon";

import styles from "./attachment-picker.module.css";

type AttachmentPickerProps = {
  attachments: { name: string; preview: string; isVideo: boolean }[];
  isFull: boolean;
  isUploading: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (name: string) => void;
};

export const AttachmentPicker = ({
  attachments,
  isFull,
  isUploading,
  onAdd,
  onRemove,
}: AttachmentPickerProps) => {
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    onAdd([...(event.target.files ?? [])]);
    event.target.value = "";
  };

  return (
    <div className={styles.Picker}>
      {attachments.map((attachment) => (
        <div key={attachment.name} className={styles.Thumb}>
          {attachment.isVideo ? (
            <video
              src={attachment.preview}
              muted
              playsInline
              preload="metadata"
            />
          ) : (
            <img src={attachment.preview} alt="" />
          )}
          <IconButton
            className={styles.Remove}
            variant="overlay"
            size="small"
            aria-label="Убрать вложение"
            onClick={() => onRemove(attachment.name)}
          >
            <Icon16CloseIos />
          </IconButton>
        </div>
      ))}

      {!isFull && (
        <label className={styles.Add}>
          <input
            type="file"
            accept="image/*,video/mp4,video/quicktime"
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
