import { Button, Flex, Input, Panel, Typography } from "@maxhub/max-ui";
import { z } from "zod";

import { plural } from "@/shared/lib/format";
import { useRouteParams } from "@/shared/lib/router";
import { Card } from "@/shared/ui/card";
import { FieldError } from "@/shared/ui/field-error";
import { buildingIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState } from "@/shared/ui/state";

import { INN_LIMIT, useOrgRegistration } from "./use-org-registration";

import styles from "./org-registration.module.css";

const OrgRegistration = ({ code }: { code: string }) => {
  const form = useOrgRegistration(code);
  const found = form.found;

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="header" color="primary">
            <h1>Регистрация УК</h1>
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Кабинет управляющей компании: заявки жителей, показания, объявления
            и аналитика по домам
          </Typography.Text>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <form onSubmit={form.search}>
            <Typography.Text asChild variant="detail-strong" color="primary">
              <label htmlFor="org-inn">ИНН организации</label>
            </Typography.Text>
            <Input
              id="org-inn"
              inputMode="numeric"
              autoComplete="off"
              maxLength={INN_LIMIT}
              placeholder="10 цифр"
              {...form.innField}
            />
            <FieldError message={form.innError} />
            <Button
              type="submit"
              size="large"
              variant={found ? "secondary" : "primary"}
              loading={form.isSearching}
            >
              Найти в реестре
            </Button>
            <Typography.Text variant="detail" color="secondary">
              Ищем среди организаций в базе Жэки: УК домов из открытых данных
              Реформы ЖКХ и демо-УК
            </Typography.Text>
          </form>
        </Flex>

        {form.searchError && (
          <Typography.Text variant="description" className={styles.Failed}>
            {form.searchError}
          </Typography.Text>
        )}

        {form.isNotFound && (
          <Card>
            <Typography.Text variant="body-strong" color="primary">
              Организация не найдена
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              В реестре нет управляющей компании с таким ИНН. Проверьте цифры
            </Typography.Text>
          </Card>
        )}

        {found && (
          <Card>
            <Flex align="center" gap={12}>
              <IconTile icon={buildingIcon} tone="themed" />
              <Flex
                className={styles.Grow}
                align="stretch"
                direction="column"
                gapY={2}
              >
                <Typography.Text variant="body-strong" color="primary">
                  {found.name}
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  ИНН {found.inn}
                  {found.license_no && ` · лицензия ${found.license_no}`}
                </Typography.Text>
              </Flex>
            </Flex>
            <Typography.Text variant="description" color="secondary">
              {found.address}
              {found.phone && ` · ${found.phone}`}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {found.houses.length > 0
                ? `В управлении ${found.houses.length} ${plural(found.houses.length, ["дом", "дома", "домов"])}`
                : "Домов в управлении пока нет"}
            </Typography.Text>
            {found.already_registered && (
              <Typography.Text variant="description" color="primary">
                Организация уже зарегистрирована. Попросите руководителя
                пригласить вас в кабинет
              </Typography.Text>
            )}
          </Card>
        )}

        {form.registerError && (
          <Typography.Text variant="description" className={styles.Failed}>
            {form.registerError}
          </Typography.Text>
        )}
      </div>

      {found && !found.already_registered && (
        <Flex
          className={styles.Footer}
          align="stretch"
          direction="column"
          gap={8}
        >
          <Button
            size="large"
            stretched
            loading={form.isRegistering}
            onClick={form.register}
          >
            Зарегистрировать
          </Button>
          <Typography.Text
            className={styles.Note}
            variant="description"
            color="secondary"
          >
            Вы станете создателем кабинета и сможете пригласить сотрудников
          </Typography.Text>
        </Flex>
      )}
    </Panel>
  );
};

const OrgRegistrationPage = () => {
  const params = useRouteParams(
    z.object({ code: z.string().regex(/^[A-Za-z0-9_-]{1,256}$/) }),
  );

  if (!params) {
    return (
      <EmptyState
        fill
        icon={buildingIcon}
        title="Ссылка регистрации повреждена"
        description="Откройте её заново из чата с ботом"
      />
    );
  }

  return <OrgRegistration code={params.code} />;
};

export const Component = OrgRegistrationPage;
