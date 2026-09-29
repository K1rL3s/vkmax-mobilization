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

const AppearancePage = () => {
  const { session, save } = useSession();
  const update = rqClient.useMutation("put", "/api/me/appearance");
  const current = update.isPending
    ? update.variables.body.text_size
    : session?.text_size;

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
                    onChange={() =>
                      update.mutate(
                        { params: authParams(), body: { text_size: size } },
                        { onSuccess: save },
                      )
                    }
                  />
                }
              />
            ))}
          </div>
        </section>
      </Flex>

      {update.isError && (
        <Typography.Text variant="description" className={styles.Error}>
          Не получилось сохранить размер. Проверьте связь и выберите ещё раз
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
        Размер сохранится в вашем профиле. Текст в чате с ботом настраивается в
        самом MAX
      </Typography.Text>
    </Panel>
  );
};

export const Component = AppearancePage;
