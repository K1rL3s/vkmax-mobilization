import { useEffect, useRef } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import {
  INVITABLE_ROLES,
  inviteBlock,
  ROLE_LABEL,
  type InvitableRole,
  type OrgRole,
} from "../domain/roles";
import {
  ACTIVATIONS,
  LIFETIMES,
  useInviteForm,
} from "../model/use-invite-form";
import { InviteCard } from "./invite-card";

import styles from "./invite-dialog.module.css";

// что роль даёт - по зависимостям ручек: дома, настройки и команда требуют
// администратора, заявки, приём, объявления и опросы открыты любому сотруднику
const ROLE_HINT: Record<InvitableRole, string> = {
  admin:
    "Дома, жители, настройки и команда. Приглашает сотрудников и исполнителей",
  employee:
    "Заявки, приём, объявления, опросы и аналитика. Дома, настройки и команда ему закрыты",
  executor:
    "Кабинета УК нет: получает назначенные заявки и отмечает выполнение в боте",
};

type Choice<T> = { value: T; label: string; disabled?: boolean };

const Chips = <T extends string | number>({
  label,
  choices,
  value,
  onChange,
}: {
  label: string;
  choices: Choice<T>[];
  value: T;
  onChange: (value: T) => void;
}) => (
  <Flex direction="column" gapY={8} role="group" aria-label={label}>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
    <Flex wrap="wrap" gap={8}>
      {choices.map((choice) => (
        <Button
          key={choice.value}
          type="button"
          size="small"
          variant={choice.value === value ? "primary" : "secondary"}
          aria-pressed={choice.value === value}
          disabled={choice.disabled}
          onClick={() => onChange(choice.value)}
        >
          {choice.label}
        </Button>
      ))}
    </Flex>
  </Flex>
);

type InviteDialogProps = {
  actor: OrgRole | undefined;
  isOpen: boolean;
  onClose: () => void;
};

export const InviteDialog = ({ actor, isOpen, onClose }: InviteDialogProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const form = useInviteForm();

  useEffect(() => {
    if (isOpen) {
      dialog.current?.showModal();
    } else {
      dialog.current?.close();
    }
  }, [isOpen]);

  const close = () => {
    form.reset();
    onClose();
  };

  const blocks = INVITABLE_ROLES.map((role) => ({
    role,
    reason: actor ? inviteBlock(actor, role) : null,
  }));
  const blocked = blocks.filter((item) => item.reason !== null);

  return (
    <dialog
      ref={dialog}
      className={styles.Dialog}
      onCancel={(event) => {
        if (form.isPending) {
          event.preventDefault();
        }
      }}
      onClose={close}
    >
      {form.created ? (
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>Ссылка готова</h2>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Отправьте её человеку в MAX. Ссылка откроет бота: он попросит
            согласие на обработку данных, если его ещё не давали, и добавит в
            команду
          </Typography.Text>

          <InviteCard
            className={styles.Result}
            invite={form.created}
            state="live"
          />

          <Button size="large" stretched onClick={close}>
            Готово
          </Button>
        </Flex>
      ) : (
        <Flex
          asChild
          direction="column"
          align="stretch"
          gapY={16}
          onSubmit={form.submit}
        >
          <form>
            <Typography.Text asChild variant="title" color="primary">
              <h2 className={styles.Title}>Пригласить в команду</h2>
            </Typography.Text>

            <Flex direction="column" gapY={8}>
              <Chips
                label="Роль"
                choices={blocks.map(({ role, reason }) => ({
                  value: role,
                  label: ROLE_LABEL[role],
                  disabled: reason !== null,
                }))}
                value={form.values.role}
                onChange={(role) => form.setValue("role", role)}
              />

              <Typography.Text variant="description" color="secondary">
                {ROLE_HINT[form.values.role]}
              </Typography.Text>

              {blocked.map(({ role, reason }) => (
                <Typography.Text
                  key={role}
                  variant="description"
                  color="tertiary"
                >
                  {reason}
                </Typography.Text>
              ))}
            </Flex>

            <Chips
              label="Сколько действует ссылка"
              choices={LIFETIMES}
              value={form.values.hours}
              onChange={(hours) => form.setValue("expires_in_hours", hours)}
            />

            <Chips
              label="Сколько человек войдёт по ссылке"
              choices={ACTIVATIONS.map((value) => ({
                value,
                label: String(value),
              }))}
              value={form.values.activations}
              onChange={(count) => form.setValue("max_activations", count)}
            />

            <Typography.Text variant="description" color="secondary">
              Тому, кто уже в команде, ссылка повысит роль, если новая выше, и
              не потратит активацию
            </Typography.Text>

            {form.error && (
              <Typography.Text className={styles.Error} variant="description">
                {form.error}
              </Typography.Text>
            )}

            <Flex direction="column" align="stretch" gapY={8}>
              <Button
                type="submit"
                size="large"
                stretched
                loading={form.isPending}
              >
                Создать ссылку
              </Button>

              <Button
                type="button"
                size="large"
                stretched
                variant="secondary"
                disabled={form.isPending}
                onClick={close}
              >
                Отмена
              </Button>
            </Flex>
          </form>
        </Flex>
      )}
    </dialog>
  );
};
