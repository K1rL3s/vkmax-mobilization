import type { ChangeEvent, ReactNode } from "react";
import {
  Button,
  CellSimple,
  Flex,
  IconButton,
  Input,
  Switch,
  Typography,
} from "@maxhub/max-ui";
import { Controller } from "react-hook-form";

import { useRequestCategories } from "@/features/request";
import { DateInput } from "@/shared/ui/date-input";
import { FieldError } from "@/shared/ui/field-error";
import { Icon, trashIcon } from "@/shared/ui/icon";

import { announcementFormConstraints } from "../domain/announcement-form-constraints";
import type { AnnouncementFormModel } from "../model/use-announcement-form";

import styles from "./works-fields.module.css";

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <Flex align="stretch" direction="column" gapY={4} className={styles.Field}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>
    {children}
  </Flex>
);

const Moment = ({
  form,
  day,
  time,
  label,
}: {
  form: AnnouncementFormModel;
  day: "worksFromDay" | "worksToDay";
  time: "worksFromTime" | "worksToTime";
  label: string;
}) => (
  <div className={styles.Pair}>
    <Field label={label}>
      <Controller
        control={form.control}
        name={day}
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

    <Field label="Время">
      <Input type="time" withClearButton={false} {...form.register(time)} />
    </Field>
  </div>
);

export const WorksFields = ({ form }: { form: AnnouncementFormModel }) => {
  const categories = useRequestCategories();
  const { documentsMax, documentTitleMax } = announcementFormConstraints;

  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const [file] = event.target.files ?? [];
    event.target.value = "";

    if (file) {
      form.addDocument(file);
    }
  };

  return (
    <>
      <div className={styles.Panel}>
        <CellSimple
          as="label"
          title="Плановые работы"
          subtitle="Срок и документы. Житель увидит предупреждение, когда выберет эту категорию в заявке"
          after={<Switch {...form.register("works")} />}
        />
      </div>

      {form.works && (
        <Flex asChild align="stretch" direction="column" gapY={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Плановые работы</h2>
            </Typography.Text>

            <div className={styles.Chips}>
              {[
                { category: null, label: "Без категории" },
                ...(categories.data ?? []).filter(
                  ({ category }) =>
                    category !== "charge_dispute" && category !== "meter_error",
                ),
              ].map(({ category, label }) => (
                <Button
                  key={category ?? "none"}
                  type="button"
                  size="small"
                  variant={
                    form.worksCategory === category ? "primary" : "secondary"
                  }
                  aria-pressed={form.worksCategory === category}
                  onClick={() => form.setWorksCategory(category)}
                >
                  {label}
                </Button>
              ))}
            </div>

            <Typography.Text variant="description" color="secondary">
              {form.worksCategory
                ? "Жители, которые выберут эту категорию в заявке, увидят, что работы идут и до какого времени"
                : "Без категории предупреждения в форме заявки не будет, только объявление"}
            </Typography.Text>

            <Moment
              form={form}
              day="worksFromDay"
              time="worksFromTime"
              label="Начало"
            />
            <Moment
              form={form}
              day="worksToDay"
              time="worksToTime"
              label="Окончание"
            />
            <FieldError message={form.errors.worksToDay?.message} />

            {form.documents.map((document, index) => (
              <div key={document.id} className={styles.Document}>
                <Input
                  placeholder="Например, приказ № 12"
                  maxLength={documentTitleMax}
                  hint={form.errors.documents?.[index]?.title?.message}
                  innerClassNames={{ hint: styles.Error }}
                  {...form.register(`documents.${index}.title`)}
                />

                <IconButton
                  variant="secondary"
                  size="small"
                  aria-label={`Убрать документ ${index + 1}`}
                  onClick={() => form.removeDocument(index)}
                >
                  <Icon src={trashIcon} size={18} />
                </IconButton>
              </div>
            ))}

            {form.documents.length < documentsMax && (
              <Button asChild size="medium" variant="secondary">
                <label>
                  <input
                    type="file"
                    accept="application/pdf"
                    hidden
                    disabled={form.isUploading}
                    onChange={pick}
                  />
                  {form.isUploading ? "Загружаем документ…" : "Приложить PDF"}
                </label>
              </Button>
            )}

            <Typography.Text
              variant="description"
              color={form.uploadError ? undefined : "secondary"}
              className={form.uploadError ? styles.Error : undefined}
            >
              {form.uploadError ||
                `Приказ или график работ: до ${documentsMax} файлов PDF. Жители откроют их из объявления`}
            </Typography.Text>
          </section>
        </Flex>
      )}
    </>
  );
};
