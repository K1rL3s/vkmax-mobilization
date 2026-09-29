import { useState } from "react";
import {
  Button,
  CellSimple,
  Flex,
  Radio,
  Textarea,
  Typography,
} from "@maxhub/max-ui";

import { BottomSheet } from "@/shared/ui/bottom-sheet";
import { FieldError } from "@/shared/ui/field-error";

import { CANCEL_REASONS, cancelFormConstraints } from "../domain/cancel";
import type { CancelReason, RequestCard } from "../domain/types";
import { useCancelRequest } from "../model/use-cancel-request";

import styles from "./cancel-panel.module.css";

export const CancelPanel = ({ request }: { request: RequestCard }) => {
  const [isOpen, setOpen] = useState(false);
  const model = useCancelRequest(request.id, () => setOpen(false));

  return (
    <>
      <Button
        size="medium"
        variant="ghost"
        stretched
        onClick={() => setOpen(true)}
      >
        Отменить заявку
      </Button>

      <BottomSheet isOpen={isOpen} onClose={() => setOpen(false)}>
        <Flex asChild align="stretch" direction="column" gapY={12}>
          <form onSubmit={model.submit} noValidate>
            <Flex direction="column" gapY={4}>
              <Typography.Text asChild variant="title" color="primary">
                <h2 className={styles.Title}>Отменить заявку №{request.id}?</h2>
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                УК и исполнитель получат сообщение с причиной
              </Typography.Text>
            </Flex>

            <div className={styles.Reasons}>
              {(Object.entries(CANCEL_REASONS) as [CancelReason, string][]).map(
                ([reason, label], index) => (
                  <CellSimple
                    key={reason}
                    as="label"
                    separator={index > 0}
                    title={label}
                    after={
                      <Radio
                        value={reason}
                        disabled={model.isPending}
                        {...model.form.register("reason")}
                      />
                    }
                  />
                ),
              )}
            </div>

            <Textarea
              mode="secondary"
              rows={3}
              maxLength={cancelFormConstraints.comment}
              placeholder={
                model.isOther
                  ? "Расскажите, почему отменяете"
                  : "Комментарий, если хотите"
              }
              disabled={model.isPending}
              aria-invalid={!!model.commentError}
              aria-label="Комментарий к отмене"
              {...model.form.register("comment")}
            />
            <FieldError message={model.commentError} />
            <FieldError message={model.error} />

            <Button
              type="submit"
              size="large"
              stretched
              variant="destructive"
              loading={model.isPending}
              disabled={!model.canSubmit}
            >
              Отменить заявку
            </Button>
            <Button
              type="button"
              size="large"
              stretched
              variant="secondary"
              disabled={model.isPending}
              onClick={() => setOpen(false)}
            >
              Не отменять
            </Button>
          </form>
        </Flex>
      </BottomSheet>
    </>
  );
};
