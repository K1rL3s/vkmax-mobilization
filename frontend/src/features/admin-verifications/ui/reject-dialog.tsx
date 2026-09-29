import { useEffect, useRef } from "react";
import { Button, Flex, Textarea, Typography } from "@maxhub/max-ui";
import { useWatch } from "react-hook-form";

import { cn } from "@/shared/lib/css";
import { endSentence } from "@/shared/lib/format";

import { verificationFormConstraints } from "../domain/verification-form-constraints";
import { useRejectForm } from "../model/use-reject-form";
import type { VerificationRequest } from "../model/use-verification-list";

import styles from "./reject-dialog.module.css";

type RejectDialogProps = {
  request: VerificationRequest;
  isPending: boolean;
  error: string | false;
  onSubmit: (reason: string) => void;
  onClose: () => void;
};

const ReasonCounter = ({
  control,
}: {
  control: ReturnType<typeof useRejectForm>["control"];
}) => {
  const reason = useWatch({ control, name: "reason" });

  return (
    <Typography.Text variant="detail" color="secondary">
      {reason.length} / {verificationFormConstraints.reasonMax}
    </Typography.Text>
  );
};

export const RejectDialog = ({
  request,
  isPending,
  error,
  onSubmit,
  onClose,
}: RejectDialogProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const form = useRejectForm(onSubmit);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  return (
    <dialog
      ref={dialog}
      className={styles.Dialog}
      onCancel={(event) => {
        if (isPending) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
    >
      <Flex
        asChild
        align="stretch"
        direction="column"
        gapY={12}
        onSubmit={form.submit}
      >
        <form>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>Отклонить запрос</h2>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Кв. {request.flat_number}, {endSentence(request.user_name)} Причину
            житель увидит в своей карточке подтверждения и получит сообщением.
          </Typography.Text>

          <Flex align="center" gap={8} wrap="wrap">
            {[
              {
                label: "Счёт не совпал",
                text: "Лицевой счёт не совпал с данными УК",
              },
              {
                label: "Счёт собственника",
                text: "Квитанция оформлена на собственника",
              },
              { label: "Нет в данных УК", text: "Квартиры нет в данных УК" },
            ].map((preset) => (
              <Button
                key={preset.label}
                type="button"
                size="small"
                variant="secondary"
                disabled={isPending}
                onClick={() => form.usePreset(preset.text)}
              >
                {preset.label}
              </Button>
            ))}
          </Flex>

          <Textarea
            rows={4}
            mode="secondary"
            placeholder="Что жителю исправить, чтобы подать заново"
            maxLength={verificationFormConstraints.reasonMax}
            disabled={isPending}
            {...form.register()}
          />

          <Flex align="center" gap={8}>
            <Typography.Text
              className={cn(styles.Grow, form.error && styles.Error)}
              variant="description"
              color={form.error ? undefined : "secondary"}
            >
              {form.error ?? "Житель подаст запрос заново, когда исправит"}
            </Typography.Text>

            <ReasonCounter control={form.control} />
          </Flex>

          {error && (
            <Typography.Text className={styles.Error} variant="description">
              {error}
            </Typography.Text>
          )}

          <Button
            type="submit"
            size="large"
            stretched
            variant="destructive"
            loading={isPending}
            disabled={!form.canSubmit}
          >
            Отклонить запрос
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
        </form>
      </Flex>
    </dialog>
  );
};
