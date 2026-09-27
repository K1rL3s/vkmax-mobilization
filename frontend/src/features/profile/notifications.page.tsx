import { CellSimple, Flex, Panel, Radio, Typography } from "@maxhub/max-ui";

import { Icon } from "@/shared/ui/icon";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import {
  ALWAYS_DELIVERED,
  CATEGORIES,
  LEVEL_LABEL,
  type NotificationLevel,
  useNotificationSettings,
} from "./use-notification-settings";

import styles from "./profile.module.css";

const LEVELS: { level: NotificationLevel; hint: string }[] = [
  { level: "sound", hint: "Придут со звуком и вибрацией" },
  { level: "silent", hint: "Придут тихо, без звука" },
  { level: "off", hint: "Бот не будет их присылать" },
];

const NotificationsPage = () => {
  const notifications = useNotificationSettings();
  const { settings } = notifications;

  if (settings.isPending) {
    return <LoadingState fill title="Загружаем настройки" />;
  }

  if (settings.isError) {
    return (
      <ErrorState
        error={settings.error}
        fill
        onRetry={() => void settings.refetch()}
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      {CATEGORIES.map(({ category, title, icon }) => (
        <Flex key={category} asChild align="stretch" direction="column" gap={8}>
          <section>
            <Flex align="center" gap={8}>
              <Icon src={icon} size={20} className={styles.CellIcon} />
              <Typography.Text asChild variant="title" color="primary">
                <h2>{title}</h2>
              </Typography.Text>
            </Flex>
            <div className={styles.Panel}>
              {LEVELS.map(({ level, hint }, index) => (
                <CellSimple
                  key={level}
                  as="label"
                  separator={index > 0}
                  title={LEVEL_LABEL[level]}
                  subtitle={hint}
                  after={
                    <Radio
                      name={category}
                      checked={notifications.levelOf(category) === level}
                      disabled={notifications.isSaving}
                      onChange={() => notifications.set(category, level)}
                    />
                  }
                />
              ))}
            </div>
          </section>
        </Flex>
      ))}

      {notifications.isFailed && (
        <Typography.Text variant="description" className={styles.Error}>
          Не получилось сохранить настройку. Проверьте связь и выберите ещё раз
        </Typography.Text>
      )}

      <Typography.Text variant="description" color="tertiary">
        {ALWAYS_DELIVERED}
      </Typography.Text>
    </Panel>
  );
};

export const Component = NotificationsPage;
