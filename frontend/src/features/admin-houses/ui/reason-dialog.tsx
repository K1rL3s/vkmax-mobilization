import { useEffect, useRef } from "react";
import { Button, Flex, Textarea, Typography } from "@maxhub/max-ui";
import { useWatch } from "react-hook-form";

import { cn } from "@/shared/lib/css";

import { reasonFormConstraints } from "../domain/resident";
import { useReasonForm } from "../model/use-reason-form";

import styles from "./sheet.module.css";

type ReasonDialogProps = {
  title: string;
  description: string;
  presets: { label: string; text: string }[];
  placeholder: string;
  submitLabel: string;
  isPending: boolean;
  error: string | null;
  onSubmit: (reason: string) => void;
  onClose: () => void;
};

const ReasonCounter = ({
  control,
}: {
  control: ReturnType<typeof useReasonForm>["control"];
}) => {
  const reason = useWatch({ control, name: "reason" });

  return (
    <Typography.Text variant="detail" color="secondary">
      {reason.length} / {reasonFormConstraints.reasonMax}
    </Typography.Text>
  );
};

export const ReasonDialog = ({
  title,
  description,
  presets,
  placeholder,
  submitLabel,
  isPending,
  error,
  onSubmit,
  onClose,
}: ReasonDialogProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const form = useReasonForm(onSubmit);

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
      <Flex
        asChild
        align="stretch"
        direction="column"
        gapY={12}
        onSubmit={form.submit}
      >
        <form>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>{title}</h2>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            {description}
          </Typography.Text>

          <Flex align="center" gap={8} wrap="wrap">
            {presets.map((preset) => (
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
            placeholder={placeholder}
            maxLength={reasonFormConstraints.reasonMax}
            disabled={isPending}
            {...form.register()}
          />

          <Flex align="center" gap={8}>
            <Typography.Text
              className={cn(styles.Grow, form.error && styles.Error)}
              variant="description"
              color={form.error ? undefined : "secondary"}
            >
              {form.error ?? "Причину житель получит сообщением от бота"}
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
            {submitLabel}
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
