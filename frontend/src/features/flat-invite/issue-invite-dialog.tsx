import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import { authParams } from "@/shared/api/instance";
import { BottomSheet } from "@/shared/ui/bottom-sheet";

import { InviteCard } from "./invite-card";
import { useIssueInvite } from "./use-flat-invites";

import styles from "./issue-invite-dialog.module.css";

type IssueInviteDialogProps = {
  flatId: number;
  isOpen: boolean;
  onClose: () => void;
};

const Chips = ({
  label,
  choices,
  value,
  onChange,
}: {
  label: string;
  choices: { value: number; label: string }[];
  value: number;
  onChange: (value: number) => void;
}) => (
  <Flex direction="column" gapY={8} role="group" aria-label={label}>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
    <Flex wrap="wrap" gap={8}>
      {choices.map((choice) => (
        <Button
          key={choice.value}
          size="small"
          variant={choice.value === value ? "primary" : "secondary"}
          aria-pressed={choice.value === value}
          onClick={() => onChange(choice.value)}
        >
          {choice.label}
        </Button>
      ))}
    </Flex>
  </Flex>
);

export const IssueInviteDialog = ({
  flatId,
  isOpen,
  onClose,
}: IssueInviteDialogProps) => {
  const [hours, setHours] = useState(72);
  const [activations, setActivations] = useState(1);
  const issue = useIssueInvite(flatId);

  const close = () => {
    issue.reset();
    onClose();
  };

  return (
    <BottomSheet isOpen={isOpen} onClose={close}>
      {issue.data ? (
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>Ссылка готова</h2>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Скопируйте ссылку и отправьте арендатору: по ней он войдёт в
            квартиру без подтверждения через УК
          </Typography.Text>

          <InviteCard className={styles.Result} invite={issue.data} />

          <Button size="large" stretched onClick={close}>
            Готово
          </Button>
        </Flex>
      ) : (
        <Flex direction="column" align="stretch" gapY={16}>
          <Flex direction="column" gapY={4}>
            <Typography.Text asChild variant="title" color="primary">
              <h2 className={styles.Title}>Приглашение в квартиру</h2>
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Арендатор войдёт в квартиру по приглашению, но не увидит
              начисления и не сможет голосовать в опросах
            </Typography.Text>
          </Flex>

          <Chips
            label="Срок действия"
            choices={[
              { value: 24, label: "1 день" },
              { value: 72, label: "3 дня" },
              { value: 168, label: "Неделя" },
            ]}
            value={hours}
            onChange={setHours}
          />
          <Chips
            label="Сколько человек сможет войти"
            choices={[1, 2, 3, 5].map((value) => ({
              value,
              label: String(value),
            }))}
            value={activations}
            onChange={setActivations}
          />

          {issue.isError && (
            <Typography.Text className={styles.Error} variant="description">
              Не получилось создать приглашение. Попробуйте ещё раз
            </Typography.Text>
          )}

          <Flex direction="column" align="stretch" gapY={8}>
            <Button
              size="large"
              stretched
              loading={issue.isPending}
              onClick={() =>
                issue.mutate({
                  params: { ...authParams(), path: { flat_id: flatId } },
                  body: {
                    expires_in_hours: hours,
                    max_activations: activations,
                  },
                })
              }
            >
              Пригласить
            </Button>
            <Button
              size="large"
              stretched
              variant="secondary"
              disabled={issue.isPending}
              onClick={close}
            >
              Отмена
            </Button>
          </Flex>
        </Flex>
      )}
    </BottomSheet>
  );
};
