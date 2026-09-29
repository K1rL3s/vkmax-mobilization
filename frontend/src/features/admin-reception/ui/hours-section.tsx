import { useState, type ReactNode } from "react";
import {
  Button,
  CellSimple,
  Flex,
  Input,
  Switch,
  Typography,
} from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { useSession } from "@/shared/model/session";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import {
  WEEKDAYS,
  dayLabel,
  receptionFormConstraints as limits,
  scheduleSummary,
  type ReceptionWindow,
} from "../domain/schedule";
import { useHoursForm } from "../model/use-hours-form";
import { useIsOrgAdmin, useReceptionWindows } from "../model/use-reception";

import { TimeChips } from "./time-chips";

import styles from "./hours-section.module.css";

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <Flex align="stretch" direction="column" gapY={4} className={styles.Field}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>
    {children}
  </Flex>
);

const HoursEditor = ({ windows }: { windows: ReceptionWindow[] }) => {
  const form = useHoursForm(windows);
  const confirm = useConfirm();
  const { draft, errors, register } = form;
  const number = { valueAsNumber: true } as const;

  const send = () => {
    confirm.dismiss();
    form.submit();
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();

        if (form.isTurningOff) {
          confirm.ask();
        } else {
          form.submit();
        }
      }}
    >
      <Flex align="stretch" direction="column" gapY={16}>
        <Flex align="stretch" direction="column" gapY={8}>
          <Typography.Text variant="detail" color="secondary">
            Какой день меняем
          </Typography.Text>

          <div className={styles.Days}>
            {WEEKDAYS.map((weekday) => (
              <button
                key={weekday.value}
                type="button"
                className={cn(
                  styles.Day,
                  weekday.value === form.weekday && styles.selected,
                )}
                aria-pressed={weekday.value === form.weekday}
                onClick={() => form.selectDay(weekday.value)}
              >
                <Typography.Text variant="description">
                  {weekday.short}
                </Typography.Text>
                <span
                  className={cn(
                    styles.Dot,
                    dayLabel(windows, weekday.value) !== null && styles.on,
                  )}
                />
              </button>
            ))}
          </div>
        </Flex>

        <CellSimple
          as="label"
          className={styles.Switch}
          title={`Принимаем ${WEEKDAYS[form.weekday].at}`}
          after={<Switch type="checkbox" {...register("enabled")} />}
        />

        {draft.enabled && (
          <>
            <div className={styles.Pair}>
              <Field label="С">
                <Input
                  type="time"
                  withClearButton={false}
                  {...register("timeFrom")}
                />
              </Field>
              <Field label="До">
                <Input
                  type="time"
                  withClearButton={false}
                  {...register("timeTo")}
                />
              </Field>
            </div>

            <CellSimple
              as="label"
              className={styles.Switch}
              title="Перерыв на обед"
              after={<Switch type="checkbox" {...register("hasBreak")} />}
            />

            {draft.hasBreak && (
              <div className={styles.Pair}>
                <Field label="Перерыв с">
                  <Input
                    type="time"
                    withClearButton={false}
                    {...register("breakFrom")}
                  />
                </Field>
                <Field label="Перерыв до">
                  <Input
                    type="time"
                    withClearButton={false}
                    {...register("breakTo")}
                  />
                </Field>
              </div>
            )}

            <div className={styles.Pair}>
              <Field label="Слот, минут">
                <Input
                  type="number"
                  inputMode="numeric"
                  min={limits.slotMin}
                  max={limits.slotMax}
                  withClearButton={false}
                  hint={errors.slotMinutes?.message}
                  innerClassNames={{ hint: styles.Error }}
                  {...register("slotMinutes", number)}
                />
              </Field>

              <Field label="Жителей сразу">
                <Input
                  type="number"
                  inputMode="numeric"
                  min={limits.capacityMin}
                  max={limits.capacityMax}
                  withClearButton={false}
                  hint={errors.capacity?.message}
                  innerClassNames={{ hint: styles.Error }}
                  {...register("capacity", number)}
                />
              </Field>
            </div>
          </>
        )}

        {form.spansError ? (
          <Typography.Text className={styles.Error} variant="description">
            {form.spansError}
          </Typography.Text>
        ) : (
          <>
            {draft.enabled && <TimeChips labels={form.slots} inCard />}
            {(!draft.enabled || form.slots.length === 0) && (
              <Typography.Text variant="description" color="secondary">
                В этот день житель записаться не сможет
              </Typography.Text>
            )}
          </>
        )}

        {form.saveError && (
          <Typography.Text className={styles.Error} variant="description">
            {form.saveError}
          </Typography.Text>
        )}

        <Button
          type="submit"
          size="medium"
          stretched
          loading={form.isSaving}
          disabled={!form.canSave}
        >
          Сохранить день
        </Button>

        {form.isSaved && (
          <Typography.Text variant="description" color="secondary">
            Часы сохранены. Житель уже видит новые слоты
          </Typography.Text>
        )}
      </Flex>

      <ConfirmDialog
        isOpen={confirm.isOpen}
        title="Выключить приём в этот день?"
        description="Слоты этого дня пропадут у жителей, записаться будет нельзя. Уже назначенные записи останутся - отменить их может только житель"
        confirmLabel="Выключить приём"
        onConfirm={send}
        onClose={confirm.dismiss}
      />
    </form>
  );
};

export const HoursSection = () => {
  const canEdit = useIsOrgAdmin();
  const isDemo = useSession().currentOrg?.is_demo;
  const windows = useReceptionWindows(canEdit);
  const [isOpen, setOpen] = useState(false);

  return (
    <section className={styles.Section}>
      <Typography.Text asChild variant="title" color="primary">
        <h2>Часы приёма</h2>
      </Typography.Text>

      {!canEdit ? (
        <div className={cn(styles.Card, styles.Muted)}>
          <Typography.Text variant="body" color="secondary">
            Часы приёма задаёт администратор организации
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Попросите его открыть эту вкладку, если расписание изменилось
          </Typography.Text>
        </div>
      ) : windows.isPending ? (
        <LoadingState title="Загружаем часы приёма" />
      ) : windows.isLoadingError ? (
        <ErrorState
          error={windows.error}
          description="Не получилось загрузить часы приёма"
          onRetry={() => void windows.refetch()}
        />
      ) : (
        <div className={styles.Card}>
          <button
            type="button"
            className={styles.Summary}
            aria-expanded={isOpen}
            disabled={isDemo}
            onClick={() => setOpen((open) => !open)}
          >
            <Typography.Text variant="body" color="primary">
              {scheduleSummary(windows.data)}
            </Typography.Text>

            {windows.data.length === 0 && (
              <Typography.Text className={styles.Error} variant="description">
                Житель не сможет записаться
              </Typography.Text>
            )}

            <Typography.Text variant="description" color="secondary">
              {isDemo
                ? "В демо-УК настройки общие для всех проверяющих и не меняются"
                : isOpen
                  ? "Свернуть"
                  : "Изменить"}
            </Typography.Text>
          </button>

          {isOpen && <HoursEditor windows={windows.data} />}
        </div>
      )}
    </section>
  );
};
