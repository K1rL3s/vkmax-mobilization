import { CellSimple, Flex, Panel, Radio, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

import styles from "./profile.module.css";

const SIZES: { size: components["schemas"]["TextSize"]; title: string }[] = [
  { size: "normal", title: "Обычный" },
  { size: "large", title: "Крупный" },
  { size: "xlarge", title: "Очень крупный" },
];

const THEMES: { theme: components["schemas"]["Theme"]; title: string }[] = [
  { theme: "system", title: "Как на телефоне" },
  { theme: "light", title: "Светлая" },
  { theme: "dark", title: "Тёмная" },
];

type Appearance = components["schemas"]["UpdateAppearanceRequest"];

const AppearancePage = () => {
  const { session, save } = useSession();
  const update = rqClient.useMutation("put", "/api/me/appearance");
  const pending: Appearance = update.isPending ? update.variables.body : {};
  const current = pending.text_size ?? session?.text_size;
  const theme = pending.theme ?? session?.theme;
  const change = (body: Appearance) =>
    update.mutate({ params: authParams(), body }, { onSuccess: save });

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Размер текста</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            {SIZES.map(({ size, title }, index) => (
              <CellSimple
                key={size}
                as="label"
                separator={index > 0}
                title={title}
                after={
                  <Radio
                    name="text_size"
                    checked={current === size}
                    onChange={() => change({ text_size: size })}
                  />
                }
              />
            ))}
          </div>
        </section>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Тема</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            {THEMES.map((item, index) => (
              <CellSimple
                key={item.theme}
                as="label"
                separator={index > 0}
                title={item.title}
                after={
                  <Radio
                    name="theme"
                    checked={theme === item.theme}
                    onChange={() => change({ theme: item.theme })}
                  />
                }
              />
            ))}
          </div>
        </section>
      </Flex>

      {update.isError && (
        <Typography.Text variant="description" className={styles.Error}>
          Не получилось сохранить. Проверьте связь и выберите ещё раз
        </Typography.Text>
      )}

      <Flex
        align="stretch"
        direction="column"
        gap={4}
        className={styles.Sample}
      >
        <Typography.Text variant="body-strong" color="primary">
          Заявка №128 принята
        </Typography.Text>
        <Typography.Text variant="body" color="primary">
          Мастер придёт завтра с 10:00 до 12:00
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Так выглядит текст в приложении
        </Typography.Text>
      </Flex>

      <Typography.Text variant="description" color="tertiary">
        Размер и тема сохранятся в вашем профиле. Чат с ботом и подложка карты
        настраиваются отдельно
      </Typography.Text>
    </Panel>
  );
};

export const Component = AppearancePage;
