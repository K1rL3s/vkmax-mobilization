import { useEffect, useRef } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import {
  type Resident,
  type ResidentActionKind,
  residentActions,
  residentPlace,
} from "../domain/resident";

import styles from "./sheet.module.css";

type ResidentSheetProps = {
  resident: Resident;
  isPending: boolean;
  error: string | null;
  onChoose: (kind: ResidentActionKind) => void;
  onClose: () => void;
};

export const ResidentSheet = ({
  resident,
  isPending,
  error,
  onChoose,
  onClose,
}: ResidentSheetProps) => {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  return (
    <dialog
      ref={dialog}
      className={styles.Sheet}
      onCancel={(event) => {
        if (isPending) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
    >
      <Flex align="stretch" direction="column" gapY={12}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>{resident.name}</h2>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            {residentPlace(resident)}
          </Typography.Text>
        </Flex>

        {residentActions(resident).map((action) => (
          <Flex key={action.kind} align="stretch" direction="column" gapY={4}>
            <Button
              size="large"
              stretched
              variant="secondary"
              innerClassNames={{
                content:
                  action.destructive && !action.refusal
                    ? styles.Error
                    : undefined,
              }}
              disabled={action.refusal !== null || isPending}
              loading={action.kind === "unblock" && isPending}
              onClick={() => onChoose(action.kind)}
            >
              {action.label}
            </Button>

            {action.refusal && (
              <Typography.Text variant="description" color="secondary">
                {action.refusal}
              </Typography.Text>
            )}
          </Flex>
        ))}

        {error && (
          <Typography.Text className={styles.Error} variant="description">
            {error}
          </Typography.Text>
        )}

        <Button
          size="large"
          stretched
          variant="ghost"
          disabled={isPending}
          onClick={onClose}
        >
          Закрыть
        </Button>
      </Flex>
    </dialog>
  );
};
