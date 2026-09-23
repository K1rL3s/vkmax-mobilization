import { Button, Typography } from "@maxhub/max-ui";

import { STATUS_LABEL, type RequestStatus } from "@/features/request";

import { STATUS_ACTION, type StatusTarget } from "../domain/request-workflow";
import { useRequestStatus } from "../model/use-request-status";

import { ChipRow } from "./chip-row";
import { FieldError } from "./field-error";

import styles from "./form-card.module.css";

export const RequestStatusAction = ({ target }: { target: StatusTarget }) => {
  const model = useRequestStatus(target);
  if (model.choices.length === 0) return null;

  const isChoice = model.choices.length > 1;
  const submit = (
    <Button stretched loading={model.isPending} onClick={() => model.submit()}>
      {isChoice ? "Применить ко всем" : STATUS_ACTION[model.choices[0]]}
    </Button>
  );

  if (!isChoice && !model.error) return submit;

  return (
    <div className={styles.Form}>
      {isChoice && (
        <>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Статус всех заявок</h2>
          </Typography.Text>
          <ChipRow
            wrap
            label="Новый статус"
            options={model.choices.map((choice) => ({
              id: choice,
              label: STATUS_LABEL[choice],
            }))}
            value={model.status}
            disabled={model.isPending}
            onChange={(choice) => model.setStatus(choice as RequestStatus)}
          />
        </>
      )}

      {target.kind === "group" && (
        <Typography.Text variant="description" color="secondary">
          Статус изменится у всех участников. Заявки, уже дошедшие до этого
          шага, останутся в нём.
        </Typography.Text>
      )}

      <FieldError message={model.error} />

      {submit}
    </div>
  );
};
