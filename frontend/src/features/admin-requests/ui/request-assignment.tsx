import { useState } from "react";
import { Button, CellSimple, Spinner, Typography } from "@maxhub/max-ui";

import { FieldError } from "@/shared/ui/field-error";
import { checkIcon, Icon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import type { AdminRequest } from "../domain/request-workflow";
import { useRequestAssignment } from "../model/use-request-assignment";

import styles from "./form-card.module.css";

export const RequestAssignment = ({ request }: { request: AdminRequest }) => {
  const model = useRequestAssignment(request);
  const [isFull, setFull] = useState(false);
  const visible = isFull ? model.executors : model.executors.slice(0, 5);
  const mark = (userId: number) => {
    if (model.pendingId === userId) return <Spinner size={20} />;
    if (model.selectedId === userId)
      return <Icon src={checkIcon} size={20} className={styles.Selected} />;
    return undefined;
  };

  return (
    <div className={styles.Form}>
      <Typography.Text asChild variant="body-strong" color="primary">
        <h2>Исполнитель</h2>
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        {request.executor_name
          ? `Работает ${request.executor_name}. Нажмите на другого, чтобы переназначить.`
          : "Не назначен. Нажмите на сотрудника - заявка уйдёт ему."}
      </Typography.Text>

      {model.isLoading && <LoadingState title="Загружаем исполнителей…" />}
      {model.isLoadError && (
        <ErrorState error={model.loadError} onRetry={model.retry} />
      )}

      {!model.isLoading &&
        !model.isLoadError &&
        model.executors.length === 0 && (
          <EmptyState
            title="Исполнителей нет"
            description="Пригласите исполнителя в настройках организации, затем обновите список."
            action={
              <Button variant="secondary" onClick={model.retry}>
                Обновить список
              </Button>
            }
          />
        )}

      <div className={styles.Cells}>
        {visible.map((executor) => (
          <CellSimple
            key={executor.user_id}
            title={executor.name}
            subtitle={`Активных заявок: ${executor.active_requests}`}
            disabled={model.isPending}
            showChevron={model.selectedId !== executor.user_id}
            after={mark(executor.user_id)}
            onClick={() => model.assign(executor.user_id)}
          />
        ))}
      </div>

      <FieldError message={model.error} />

      {model.executors.length > visible.length && (
        <Button
          className={styles.Inline}
          size="small"
          variant="secondary"
          onClick={() => setFull(true)}
        >
          Показать всех · {model.executors.length}
        </Button>
      )}
    </div>
  );
};
