import type { ReactNode } from "react";
import { Button, Flex, Input, Panel, Typography } from "@maxhub/max-ui";
import { Controller } from "react-hook-form";

import { isForbidden } from "@/shared/api/errors";
import { DateInput } from "@/shared/ui/date-input";
import { FieldError } from "@/shared/ui/field-error";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { visitFormConstraints as limits } from "./domain/visit-form";
import { useAdminRequest } from "./model/use-admin-request";
import { useVisitForm } from "./model/use-visit-form";
import { NoOrgAccess } from "./ui/no-org-access";

import styles from "./admin-request-visit.module.css";

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <Flex align="stretch" direction="column" gapY={4} className={styles.Field}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>
    {children}
  </Flex>
);

const VisitForm = ({ requestId }: { requestId: number }) => {
  const model = useVisitForm(requestId);
  const { form } = model;
  const errors = form.formState.errors;

  return (
    <form className={styles.Form} onSubmit={model.submit} noValidate>
      <Field label="День">
        <Controller
          control={form.control}
          name="date"
          render={({ field }) => (
            <DateInput
              withClearButton={false}
              name={field.name}
              value={field.value}
              onChange={field.onChange}
              onBlur={field.onBlur}
            />
          )}
        />
      </Field>
      <FieldError message={errors.date?.message} />

      <div className={styles.Pair}>
        <Field label="С">
          <Input
            type="time"
            withClearButton={false}
            {...form.register("timeFrom")}
          />
        </Field>
        <Field label="До">
          <Input
            type="time"
            withClearButton={false}
            {...form.register("timeTo")}
          />
        </Field>
      </div>
      <FieldError message={errors.timeFrom?.message} />
      <FieldError message={errors.timeTo?.message} />

      <Field label="Окно, минут">
        <Input
          type="number"
          inputMode="numeric"
          min={limits.minutesMin}
          max={limits.minutesMax}
          withClearButton={false}
          {...form.register("minutes", { valueAsNumber: true })}
        />
      </Field>
      <FieldError message={errors.minutes?.message} />

      {model.labels.length > 0 && (
        <div className={styles.Chips}>
          {model.labels.map((label) => (
            <Typography.Text
              key={label}
              className={styles.Chip}
              variant="description"
              color="primary"
            >
              {label}
            </Typography.Text>
          ))}
        </div>
      )}

      <FieldError message={model.error} />

      <Button
        type="submit"
        size="large"
        stretched
        className={styles.Submit}
        loading={model.isSubmitting}
      >
        Предложить время
      </Button>
    </form>
  );
};

const visitHint = (request: { id: number; visit?: unknown }) => {
  const hint = `Заявка №${request.id}. Житель выберет одно окно в боте или в приложении, все окна - в один день`;

  return request.visit
    ? `${hint}. Новое время заменит предложенное раньше`
    : hint;
};

const AdminRequestVisitPage = () => {
  const { valid, query } = useAdminRequest();
  if (!valid)
    return (
      <EmptyState
        fill
        title="Неверный адрес заявки"
        description="Откройте заявку из списка."
      />
    );
  if (isForbidden(query.error)) return <NoOrgAccess />;
  if (query.isPending) return <LoadingState fill title="Загружаем заявку…" />;
  if (query.isLoadingError)
    return (
      <ErrorState
        error={query.error}
        fill
        onRetry={() => void query.refetch()}
      />
    );
  if (!query.data.can_propose_visit)
    return (
      <EmptyState
        fill
        title="Время визита не предложить"
        description="Визит предлагают по личной открытой заявке жителя."
      />
    );

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>Время визита</h1>
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {visitHint(query.data)}
        </Typography.Text>
      </Flex>

      <VisitForm requestId={query.data.id} />
    </Panel>
  );
};

export const Component = AdminRequestVisitPage;
