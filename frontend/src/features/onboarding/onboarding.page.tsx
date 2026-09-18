import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Checkbox } from "@/shared/ui/checkbox";
import { buildingIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState } from "@/shared/ui/state";

import { useConsent } from "./model/use-consent";

import styles from "./onboarding.module.css";

const OnboardingPage = () => {
  const consent = useConsent();

  return (
    <Panel className={styles.Page} centeredX centeredY>
      <Flex
        className={styles.Content}
        direction="column"
        align="center"
        gap={36}
      >
        <IconTile icon={buildingIcon} tone="secondary" size="xlarge" />

        <Flex
          className={styles.Hero}
          direction="column"
          align="center"
          gapY={6}
        >
          <Typography.Text asChild variant="header" color="primary">
            <h1>Жека Коммуналкин</h1>
          </Typography.Text>

          <Typography.Text variant="body" color="secondary">
            Всё для вашего дома в одном чате: заявки в УК, показания счётчиков,
            опросы жильцов
          </Typography.Text>
        </Flex>

        <Flex
          className={styles.Footer}
          align="stretch"
          direction="column"
          gap={16}
        >
          <Checkbox
            className={styles.Consent}
            checked={consent.checked}
            disabled={consent.accepted}
            onChange={consent.setChecked}
          >
            <Typography.Text variant="description" color="primary">
              Соглашаюсь на обработку персональных данных
            </Typography.Text>

            <Typography.Text asChild variant="description">
              <Link className={styles.Policy} to={Routes.PRIVACY}>
                Политика обработки данных
              </Link>
            </Typography.Text>
          </Checkbox>

          {consent.isError && (
            <ErrorState
              title="Не получилось сохранить согласие"
              description="Проверьте связь и попробуйте ещё раз"
              onRetry={consent.start}
            />
          )}

          <Button
            size="large"
            stretched
            loading={consent.isPending}
            disabled={!consent.checked}
            onClick={consent.start}
          >
            Добавить недвижимость
          </Button>
        </Flex>
      </Flex>
    </Panel>
  );
};

export const Component = OnboardingPage;
