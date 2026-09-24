import {
  Button,
  Flex,
  Input,
  Panel,
  Textarea,
  Typography,
} from "@maxhub/max-ui";

import { Autocomplete } from "@/shared/ui/autocomplete";
import { FieldError } from "@/shared/ui/field-error";
import { searchOutlineIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { requestFormConstraints } from "./domain/request-form-constraints";
import { usePhoneRequest } from "./model/use-phone-request";
import { ChipRow } from "./ui/chip-row";

import styles from "./admin-requests.module.css";

const AdminRequestPhonePage = () => {
  const model = usePhoneRequest();
  const { form } = model;
  const errors = form.formState.errors;

  if (model.isPending)
    return <LoadingState fill title="Загружаем форму заявки…" />;
  if (model.isError) return <ErrorState fill onRetry={model.retry} />;
  if (model.categories.length === 0)
    return (
      <EmptyState
        fill
        title="Категории пока недоступны"
        description="Обновите справочник и попробуйте создать заявку снова."
        action={
          <Button variant="secondary" onClick={model.retry}>
            Обновить справочник
          </Button>
        }
      />
    );

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="header" color="primary">
        <h1>Заявка по звонку</h1>
      </Typography.Text>

      <Flex asChild align="stretch" direction="column" gap={16}>
        <form onSubmit={model.submit} noValidate>
          <Flex asChild align="stretch" direction="column" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Что случилось</h2>
              </Typography.Text>

              <Autocomplete
                placeholder="Улица и номер дома"
                icon={searchOutlineIcon}
                disabled={model.isSubmitting}
                value={model.houseSearch.query}
                onChange={model.houseSearch.change}
                options={model.houseSearch.options}
                onSelect={(option) => model.houseSearch.select(option.id)}
                status={model.houseSearch.status}
                onRetry={model.houseSearch.retry}
                loadingText="Ищем адреса…"
                emptyTitle="Дом не найден"
                emptyDescription="Проверьте название улицы или введите только её часть"
              />
              <FieldError message={errors.houseId?.message} />

              <Typography.Text variant="description" color="secondary">
                Категория
              </Typography.Text>
              <ChipRow
                wrap
                label="Категория"
                options={model.categories.map(({ category, label }) => ({
                  id: category,
                  label,
                }))}
                value={model.category}
                disabled={model.isSubmitting}
                onChange={model.selectCategory}
              />
              <FieldError message={errors.category?.message} />

              <Flex asChild align="stretch" direction="column" gap={4}>
                <label>
                  <Typography.Text variant="description" color="secondary">
                    Описание проблемы
                  </Typography.Text>
                  <Textarea
                    mode="secondary"
                    rows={4}
                    autoComplete="off"
                    placeholder="Что произошло и где нужна помощь…"
                    maxLength={requestFormConstraints.description}
                    {...form.register("description")}
                    disabled={model.isSubmitting}
                    aria-invalid={!!errors.description}
                  />
                </label>
              </Flex>
              <FieldError message={errors.description?.message} />
            </section>
          </Flex>

          <Flex asChild align="stretch" direction="column" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Кто позвонил</h2>
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                Выберите квартиру и жителя или укажите имя и телефон звонившего.
                Выбранный житель получит уведомление в MAX и сможет принять
                работу.
              </Typography.Text>

              {model.hasHouse && (
                <>
                  <Autocomplete
                    placeholder="Номер квартиры, необязательно"
                    inputMode="numeric"
                    disabled={model.isSubmitting}
                    value={model.flatSearch.query}
                    onChange={model.flatSearch.change}
                    options={model.flatSearch.options}
                    onSelect={(option) => model.flatSearch.select(option.id)}
                    status={model.flatSearch.status}
                    onRetry={model.flatSearch.retry}
                    loadingText="Ищем квартиру…"
                    emptyTitle="Квартира не найдена"
                    emptyDescription="Управляющая компания могла ещё не завести её в системе"
                  />
                  <FieldError message={errors.flatId?.message} />

                  <Autocomplete
                    placeholder="Имя жителя, необязательно"
                    disabled={model.isSubmitting}
                    value={model.residentSearch.query}
                    onChange={model.residentSearch.change}
                    options={model.residentSearch.options}
                    onSelect={(option) =>
                      model.residentSearch.select(option.id)
                    }
                    status={model.residentSearch.status}
                    onRetry={model.residentSearch.retry}
                    loadingText="Ищем жителя…"
                    emptyTitle="Житель не найден"
                    emptyDescription="В этой квартире нет подтверждённых жителей"
                  />
                  <FieldError message={errors.residentId?.message} />
                </>
              )}

              <Flex asChild align="stretch" direction="column" gap={4}>
                <label>
                  <Typography.Text variant="description" color="secondary">
                    Имя звонившего
                  </Typography.Text>
                  <Input
                    autoComplete="off"
                    maxLength={requestFormConstraints.callerName}
                    placeholder="Как представился звонивший…"
                    {...form.register("callerName")}
                    disabled={model.isSubmitting}
                    aria-invalid={!!errors.callerName}
                  />
                </label>
              </Flex>
              <FieldError message={errors.callerName?.message} />

              <Flex asChild align="stretch" direction="column" gap={4}>
                <label>
                  <Typography.Text variant="description" color="secondary">
                    Телефон звонившего
                  </Typography.Text>
                  <Input
                    type="tel"
                    autoComplete="off"
                    maxLength={requestFormConstraints.callerPhone}
                    placeholder="Номер для обратного звонка…"
                    {...form.register("callerPhone")}
                    disabled={model.isSubmitting}
                    aria-invalid={!!errors.callerPhone}
                  />
                </label>
              </Flex>
              <FieldError message={errors.callerPhone?.message} />
            </section>
          </Flex>

          <FieldError message={model.error} />

          <Button type="submit" stretched loading={model.isSubmitting}>
            Создать заявку
          </Button>
        </form>
      </Flex>
    </Panel>
  );
};

export const Component = AdminRequestPhonePage;
