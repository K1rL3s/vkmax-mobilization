import type { ReactNode } from "react";
import {
  Button,
  Flex,
  Input,
  Switch,
  Textarea,
  Typography,
} from "@maxhub/max-ui";
import { useWatch } from "react-hook-form";

import { plural } from "@/shared/lib/format";

import { orgFormConstraints as limits } from "../domain/org-form-constraints";
import { useSettingsForm, type OrgSettings } from "../model/use-settings-form";

import styles from "./settings-form.module.css";

type SettingsFormProps = {
  settings: OrgSettings;
  readOnly: boolean;
};

type Watched = ReturnType<typeof useSettingsForm>["watched"];

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <Flex align="stretch" direction="column" gapY={4}>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
    {children}
  </Flex>
);

const Section = ({
  id,
  title,
  note,
  children,
}: {
  id?: string;
  title: string;
  note: string;
  children: ReactNode;
}) => (
  <Flex asChild align="stretch" direction="column" gapY={8}>
    <section id={id} className={styles.Section}>
      <Typography.Text asChild variant="title" color="primary">
        <h2>{title}</h2>
      </Typography.Text>
      <div className={styles.Card}>{children}</div>
      <Typography.Text variant="description" color="secondary">
        {note}
      </Typography.Text>
    </section>
  </Flex>
);

const valid = (value: number, min: number, max: number) =>
  Number.isInteger(value) && value >= min && value <= max;

const windowNote = ({ alwaysOpen, dayFrom, dayTo }: Watched) => {
  if (alwaysOpen)
    return "Показания принимаются в любой день. Бот напомнит жителям 1-го числа и за 2 дня до конца месяца";
  if (
    !valid(dayFrom, limits.dayMin, limits.dayMax) ||
    !valid(dayTo, limits.dayMin, limits.dayMax)
  )
    return "Жители передают показания только в эти дни месяца";
  if (dayFrom > dayTo)
    return `Окно переходит через конец месяца: с ${dayFrom}-го по ${dayTo}-е следующего. Показания идут за месяц, в котором окно открылось`;

  return `Жители передают показания с ${dayFrom}-го по ${dayTo}-е число. Бот напомнит в первый день окна и за 2 дня до конца`;
};

const groupNote = ({ threshold, windowHours }: Watched) => {
  if (
    !valid(threshold, limits.thresholdMin, limits.thresholdMax) ||
    !valid(windowHours, limits.windowHoursMin, limits.windowHoursMax)
  )
    return "Похожие заявки из разных квартир одного дома объединяются в одну коллективную";

  return `Если за ${windowHours} ${plural(windowHours, ["час", "часа", "часов"])} из ${threshold} разных ${plural(threshold, ["квартиры", "квартир", "квартир"])} одного дома придут заявки одной категории, они объединятся в коллективную заявку`;
};

const NoteCounter = ({
  control,
}: {
  control: ReturnType<typeof useSettingsForm>["control"];
}) => {
  const note = useWatch({ control, name: "reception_note" });

  return (
    <Typography.Text
      className={styles.Counter}
      variant="detail"
      color="secondary"
    >
      {note.length} / {limits.receptionNote}
    </Typography.Text>
  );
};

export const SettingsForm = ({ settings, readOnly }: SettingsFormProps) => {
  const form = useSettingsForm(settings, readOnly);
  const { errors, register, watched } = form;
  const number = { valueAsNumber: true } as const;

  return (
    <Flex asChild align="stretch" direction="column" gapY={24}>
      <form noValidate onSubmit={form.submit}>
        <Section
          id="meter-window"
          title="Окно подачи показаний"
          note={windowNote(watched)}
        >
          <label className={styles.Switch}>
            <Typography.Text variant="body" color="primary">
              Принимать весь месяц
            </Typography.Text>
            <Switch type="checkbox" {...register("meter_window_always_open")} />
          </label>

          <div className={styles.Pair}>
            <Field label="С какого числа">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.dayMin}
                max={limits.dayMax}
                withClearButton={false}
                hint={errors.meter_window_day_from?.message}
                innerClassNames={{ hint: styles.Error }}
                {...register("meter_window_day_from", number)}
                disabled={readOnly || watched.alwaysOpen}
              />
            </Field>

            <Field label="По какое число">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.dayMin}
                max={limits.dayMax}
                withClearButton={false}
                hint={errors.meter_window_day_to?.message}
                innerClassNames={{ hint: styles.Error }}
                {...register("meter_window_day_to", number)}
                disabled={readOnly || watched.alwaysOpen}
              />
            </Field>
          </div>
        </Section>

        <Section title="Коллективные заявки" note={groupNote(watched)}>
          <div className={styles.Pair}>
            <Field label="Сколько квартир">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.thresholdMin}
                max={limits.thresholdMax}
                withClearButton={false}
                hint={errors.group_threshold?.message}
                innerClassNames={{ hint: styles.Error }}
                {...register("group_threshold", number)}
              />
            </Field>

            <Field label="За сколько часов">
              <Input
                type="number"
                inputMode="numeric"
                min={limits.windowHoursMin}
                max={limits.windowHoursMax}
                withClearButton={false}
                hint={errors.group_window_hours?.message}
                innerClassNames={{ hint: styles.Error }}
                {...register("group_window_hours", number)}
              />
            </Field>
          </div>
        </Section>

        <Section
          title="Контакты для жителей"
          note="Жители видят эти контакты в карточке дома. Аварийный номер ещё и на экране «Авария» в приложении и в боте"
        >
          <Field label="Телефон">
            <Input
              type="tel"
              inputMode="tel"
              maxLength={limits.phone}
              hint={errors.phone?.message}
              innerClassNames={{ hint: styles.Error }}
              {...register("phone")}
            />
          </Field>

          <Field label="Телефон аварийной службы">
            <Input
              type="tel"
              inputMode="tel"
              placeholder="Если есть круглосуточная диспетчерская"
              maxLength={limits.phone}
              hint={errors.emergency_phone?.message}
              innerClassNames={{ hint: styles.Error }}
              {...register("emergency_phone")}
            />
          </Field>

          <Field label="Почта">
            <Input
              type="email"
              inputMode="email"
              placeholder="Куда жители пишут письма"
              maxLength={limits.email}
              hint={errors.email?.message}
              innerClassNames={{ hint: styles.Error }}
              {...register("email")}
            />
          </Field>

          <Field label="Сайт">
            <Input
              type="url"
              inputMode="url"
              placeholder="uk-primer.ru"
              maxLength={limits.site}
              hint={errors.site?.message}
              innerClassNames={{ hint: styles.Error }}
              {...register("site")}
            />
          </Field>

          <Field label="Часы приёма">
            <Textarea
              rows={3}
              mode="secondary"
              placeholder="Например: пн-чт 9:00-18:00, пт до 17:00"
              maxLength={limits.receptionNote}
              {...register("reception_note")}
            />
            <NoteCounter control={form.control} />
          </Field>
        </Section>

        <Flex align="stretch" direction="column" gapY={8}>
          {form.saveError && (
            <Typography.Text className={styles.Error} variant="description">
              {form.saveError}
            </Typography.Text>
          )}

          <Button
            type="submit"
            size="large"
            stretched
            loading={form.isSaving}
            disabled={!form.canSave}
          >
            Сохранить настройки
          </Button>

          {form.hint && (
            <Typography.Text variant="description" color="secondary">
              {form.hint}
            </Typography.Text>
          )}
        </Flex>
      </form>
    </Flex>
  );
};
