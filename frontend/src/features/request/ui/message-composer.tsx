import type { UseFormRegisterReturn } from "react-hook-form";
import { Textarea } from "@maxhub/max-ui";

import { arrowUpIcon, Icon } from "@/shared/ui/icon";

import styles from "./message-composer.module.css";

export type MessageComposerMode = "primary" | "secondary";

export const MessageComposer = ({
  field,
  placeholder,
  maxLength,
  invalid,
  canSend,
  mode = "primary",
}: {
  field: UseFormRegisterReturn;
  placeholder: string;
  maxLength: number;
  invalid: boolean;
  canSend: boolean;
  mode?: MessageComposerMode;
}) => (
  <div className={styles.Composer}>
    <Textarea
      className={styles[mode]}
      rows={3}
      maxLength={maxLength}
      autoComplete="off"
      placeholder={placeholder}
      aria-label={placeholder}
      aria-invalid={invalid}
      {...field}
    />
    <button
      className={styles.Send}
      type="submit"
      disabled={!canSend}
      aria-label="Отправить"
    >
      <Icon src={arrowUpIcon} size={20} />
    </button>
  </div>
);
