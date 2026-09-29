import type { ReactNode } from "react";
import {
  Button,
  CellSimple,
  Flex,
  Input,
  Panel,
  Textarea,
  Typography,
} from "@maxhub/max-ui";
import { Controller } from "react-hook-form";

import { plural } from "@/shared/lib/format";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { DateInput } from "@/shared/ui/date-input";
import { FieldError } from "@/shared/ui/field-error";
import { checkIcon, Icon } from "@/shared/ui/icon";

import {
  accessFormConstraints as limits,
  windowLabel,
} from "../domain/access-form";
import { useAccessForm } from "../model/use-access-form";
import { FlatPicker } from "./flat-picker";

import styles from "./access-form.module.css";

type OrgHouse = { id: number; address: string; flats_count: number };

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <Flex align="stretch" direction="column" gapY={4} className={styles.Field}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>
    {children}
  </Flex>
);

export const AccessForm = ({ houses }: { houses: OrgHouse[] }) => {
  const form = useAccessForm(houses.map((house) => house.id));
  const house = houses.find((item) => item.id === form.houseId);
  const number = { valueAsNumber: true } as const;

  return (
    <Panel className={styles.Page} mode="secondary">
      <form className={styles.Form} noValidate onSubmit={form.submit}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="title" color="primary">
            <h1 className={styles.Title}>Сбор доступа</h1>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Жители выберут окно сами. Уведомление уйдёт им сразу после создания
            сбора
          </Typography.Text>
        </Flex>

        <section className={styles.Section}>
          <Typography.Text asChild variant="body-strong" color="primary">
            <h2 className={styles.Title}>Дом</h2>
          </Typography.Text>

          {houses.length === 1 ? (
            <Typography.Text variant="body" color="secondary">
              {houses[0].address}
            </Typography.Text>
          ) : (
            <div className={styles.Cells}>
              {houses.map((item) => (
                <CellSimple
                  key={item.id}
                  title={item.address}
                  subtitle={`${item.flats_count} ${plural(item.flats_count, ["квартира", "квартиры", "квартир"])}`}
                  showChevron={item.id !== form.houseId}
                  after={
                    item.id === form.houseId && (
                      <Icon
                        src={checkIcon}
                        size={20}
                        className={styles.Selected}
                      />
                    )
                  }
                  onClick={() => form.selectHouse(item.id)}
                />
              ))}
            </div>
          )}

          <FieldError message={form.errors.houseId?.message} />
        </section>

        <section className={styles.Section}>
          <Typography.Text asChild variant="body-strong" color="primary">
            <h2 className={styles.Title}>Зачем нужен доступ</h2>
          </Typography.Text>

          <Textarea
            mode="secondary"
            rows={3}
            maxLength={limits.reasonMax}
            placeholder="Что будут делать в квартире и сколько это займёт"
            {...form.register("reason")}
          />

          <Flex align="flex-start" gap={8}>
            <div className={styles.Grow}>
              <FieldError message={form.errors.reason?.message} />
            </div>

            <Typography.Text variant="detail" color="secondary">
              {form.reason.length} / {limits.reasonMax}
            </Typography.Text>
          </Flex>
        </section>

        <section className={styles.Section}>
          <Typography.Text asChild variant="body-strong" color="primary">
            <h2 className={styles.Title}>Когда придём</h2>
          </Typography.Text>

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

          <FieldError message={form.errors.date?.message} />

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

          <div className={styles.Pair}>
            <Field label="Окно, минут">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.windowMinutesMin}
                max={limits.windowMinutesMax}
                withClearButton={false}
                {...form.register("windowMinutes", number)}
              />
            </Field>

            <Field label="Квартир в окно">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.perWindowMin}
                max={limits.perWindowMax}
                withClearButton={false}
                {...form.register("perWindow", number)}
              />
            </Field>
          </div>

          <FieldError message={form.errors.timeTo?.message} />
          <FieldError message={form.errors.windowMinutes?.message} />
          <FieldError message={form.errors.perWindow?.message} />

          {form.windows.length > 0 && (
            <>
              <div className={styles.Chips}>
                {form.windows.map((startsAt) => (
                  <Typography.Text
                    key={startsAt}
                    className={styles.Chip}
                    variant="description"
                    color="primary"
                  >
                    {windowLabel(startsAt, form.windowMinutes)}
                  </Typography.Text>
                ))}
              </div>

              <Typography.Text variant="detail" color="secondary">
                Столько окон увидят жители. Каждый выберет одно
              </Typography.Text>
            </>
          )}
        </section>

        <section className={styles.Section}>
          <Typography.Text asChild variant="body-strong" color="primary">
            <h2 className={styles.Title}>В какие квартиры</h2>
          </Typography.Text>

          {house ? (
            <FlatPicker
              houseId={house.id}
              flatsCount={house.flats_count}
              selected={form.flats}
              onToggle={form.toggleFlat}
            />
          ) : (
            <Typography.Text variant="description" color="secondary">
              Сначала выберите дом: квартиры показываются по нему
            </Typography.Text>
          )}

          <FieldError message={form.errors.flats?.message} />
        </section>

        <Button type="submit" size="large" stretched>
          Собрать доступ
        </Button>
      </form>

      <ConfirmDialog
        isOpen={form.isOpen}
        title="Отправить сбор жителям?"
        description={`Жители ${form.draft?.flats.length ?? 0} ${plural(form.draft?.flats.length ?? 0, ["квартиры", "квартир", "квартир"])} получат уведомление. Отменить сбор и поменять окна потом нельзя`}
        confirmLabel="Собрать доступ"
        isPending={form.isSending}
        error={form.sendError}
        onConfirm={form.send}
        onClose={form.dismiss}
      />
    </Panel>
  );
};
