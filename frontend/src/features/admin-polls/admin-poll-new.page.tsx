import {
  Button,
  CellSimple,
  Flex,
  IconButton,
  Input,
  Panel,
  Radio,
  Switch,
  Textarea,
  Typography,
} from "@maxhub/max-ui";
import { Controller, useWatch, type Control } from "react-hook-form";

import { pollFormConstraints } from "@/features/meetings";
import { DateInput } from "@/shared/ui/date-input";
import { buildingIcon, Icon, trashIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { useAdminPollForm, type AdminPollDraft } from "./use-admin-poll-form";

import styles from "./admin-poll-new.module.css";

const DescriptionCounter = ({
  control,
}: {
  control: Control<AdminPollDraft>;
}) => {
  const description = useWatch({ control, name: "description" });

  return (
    <Typography.Text
      className={styles.Counter}
      variant="detail"
      color="secondary"
    >
      {description.length} / {pollFormConstraints.description}
    </Typography.Text>
  );
};

const AdminPollNewPage = () => {
  const form = useAdminPollForm();

  if (form.isHousesPending) {
    return <LoadingState fill title="Загружаем дома" />;
  }

  if (form.isHousesError) {
    return (
      <ErrorState error={form.housesError} fill onRetry={form.retryHouses} />
    );
  }

  if (form.houses.length === 0) {
    return (
      <Panel className={styles.Page} mode="secondary">
        <div className={styles.Content}>
          <EmptyState
            fill
            icon={buildingIcon}
            title="Опрос не для кого проводить"
            description="Опрос идёт по одному дому, а у организации пока нет домов. Когда дом появится во вкладке «Дома», его можно будет выбрать здесь."
          />

          <Typography.Text variant="description" color="secondary">
            Опрос - предварительный сбор позиций собственников и не является
            общим собранием (ОСС) по ЖК РФ
          </Typography.Text>
        </div>
      </Panel>
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Дом</h2>
            </Typography.Text>

            <div className={styles.Panel}>
              {form.houses.map((house, index) => (
                <CellSimple
                  key={house.id}
                  as="label"
                  separator={index > 0}
                  before={
                    <Radio
                      value={String(house.id)}
                      {...form.register("houseId")}
                    />
                  }
                  title={house.address}
                />
              ))}
            </div>

            <Typography.Text
              className={form.errors.houseId && styles.Error}
              variant="description"
              color={form.errors.houseId ? undefined : "secondary"}
            >
              {form.errors.houseId?.message ??
                "Голосовать смогут собственники квартир этого дома"}
            </Typography.Text>
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>О чём опрос</h2>
            </Typography.Text>

            <Input
              placeholder="Например: замена лифтов"
              maxLength={pollFormConstraints.title}
              hint={form.errors.title?.message}
              innerClassNames={{ hint: styles.Error }}
              {...form.register("title")}
            />

            <Textarea
              rows={3}
              mode="secondary"
              placeholder="Объясните жителям, о чём речь. Необязательно"
              maxLength={pollFormConstraints.description}
              {...form.register("description")}
            />

            <DescriptionCounter control={form.control} />
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Варианты ответа</h2>
            </Typography.Text>

            {form.options.map((option, index) => (
              <div key={option.id} className={styles.OptionRow}>
                <Input
                  placeholder={`Вариант ${index + 1}`}
                  maxLength={pollFormConstraints.option}
                  hint={form.errors.options?.[index]?.text?.message}
                  innerClassNames={{ hint: styles.Error }}
                  {...form.registerOption(index)}
                />

                {form.canRemoveOption && (
                  <IconButton
                    variant="secondary"
                    size="small"
                    aria-label={`Убрать вариант ${index + 1}`}
                    onClick={() => form.removeOption(index)}
                  >
                    <Icon src={trashIcon} size={18} />
                  </IconButton>
                )}
              </div>
            ))}

            <Button
              size="medium"
              variant="secondary"
              disabled={!form.canAddOption}
              onClick={form.addOption}
            >
              Добавить вариант
            </Button>

            <Typography.Text
              className={form.optionsError && styles.Error}
              variant="description"
              color={form.optionsError ? undefined : "secondary"}
            >
              {form.optionsError ??
                `От ${pollFormConstraints.optionsMin} до ${pollFormConstraints.optionsMax} вариантов`}
            </Typography.Text>

            <div className={styles.Panel}>
              <CellSimple
                as="label"
                title="Несколько вариантов"
                subtitle="Житель сможет отметить больше одного"
                after={<Switch {...form.register("isMultiple")} />}
              />
            </div>
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>До какого дня</h2>
            </Typography.Text>

            <Controller
              control={form.control}
              name="endsAt"
              render={({ field }) => (
                <DateInput
                  hint={form.errors.endsAt?.message}
                  innerClassNames={{ hint: styles.Error }}
                  name={field.name}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                />
              )}
            />

            <Typography.Text variant="description" color="secondary">
              Опрос завершится в конце выбранного дня, раньше его можно
              завершить вручную
            </Typography.Text>
          </section>
        </Flex>

        <div className={styles.Panel}>
          <CellSimple
            as="label"
            title="Сообщить жителям в личку"
            subtitle="Объявление с кнопкой «Проголосовать» и реестр, каким квартирам оно дошло"
            after={<Switch {...form.register("notifyResidents")} />}
          />
        </div>

        <Typography.Text variant="description" color="secondary">
          Жители увидят пометку: опрос - предварительный сбор позиций
          собственников и не является общим собранием (ОСС) по ЖК РФ
        </Typography.Text>

        {form.submitError && (
          <Typography.Text className={styles.Error} variant="description">
            {form.submitError}
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isSubmitting}
          onClick={form.submit}
        >
          Создать опрос
        </Button>
      </div>
    </Panel>
  );
};

export const Component = AdminPollNewPage;
