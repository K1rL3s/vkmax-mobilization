import { useEffect, useRef, type ReactNode } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import styles from "./confirm-dialog.module.css";

type ConfirmDialogProps = {
  isOpen: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  error?: ReactNode;
  isPending?: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

export const ConfirmDialog = ({
  isOpen,
  title,
  description,
  confirmLabel,
  error,
  isPending = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) => {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (isOpen) {
      dialog.current?.showModal();
    } else {
      dialog.current?.close();
    }
  }, [isOpen]);

  return (
    <dialog ref={dialog} className={styles.Dialog} onClose={onClose}>
      <Flex direction="column" align="stretch" gapY={12}>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>{title}</h2>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {description}
        </Typography.Text>

        {error && (
          <Typography.Text className={styles.Error} variant="description">
            {error}
          </Typography.Text>
        )}

        <Button
          type="button"
          size="large"
          stretched
          variant="destructive"
          loading={isPending}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>

        <Button
          type="button"
          size="large"
          stretched
          variant="secondary"
          disabled={isPending}
          onClick={onClose}
        >
          Отмена
        </Button>
      </Flex>
    </dialog>
  );
};
