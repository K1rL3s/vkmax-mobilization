import { useEffect, useRef } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { Residency } from "@/shared/model/session";

import styles from "./unlink-dialog.module.css";

type UnlinkDialogProps = {
  target: Residency | null;
  isPending: boolean;
  isFailed: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

export const UnlinkDialog = ({
  target,
  isPending,
  isFailed,
  onConfirm,
  onClose,
}: UnlinkDialogProps) => {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (target) {
      dialog.current?.showModal();
    } else {
      dialog.current?.close();
    }
  }, [target]);

  return (
    <dialog ref={dialog} className={styles.Dialog} onClose={onClose}>
      <Flex direction="column" align="stretch" gapY={12}>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>Отвязаться от дома?</h2>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Заявки и показания останутся. Чтобы указать другую квартиру,
          привяжитесь к дому заново.
          {target?.verified &&
            " Подтверждение квартиры при этом слетит — получать его придётся снова."}
        </Typography.Text>

        {isFailed && (
          <Typography.Text variant="description" className={styles.Failed}>
            Не получилось отвязаться. Проверьте связь и попробуйте ещё раз
          </Typography.Text>
        )}

        <Button
          size="large"
          stretched
          variant="destructive"
          loading={isPending}
          onClick={onConfirm}
        >
          Отвязаться
        </Button>

        <Button
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
