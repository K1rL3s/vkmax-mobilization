import { Button, Flex, IconButton, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";
import { Card } from "@/shared/ui/card";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { checkIcon, copyIcon, Icon, usersIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./chat-section.module.css";

type HouseCard = components["schemas"]["AdminHouseCard"];

// шаги повторяют бота: on_bot_added пишет добавившему в личку и выходит из
// чата, если тот бота не запускал или он ни житель, ни сотрудник УК
const STEPS = [
  "Добавьте бота в чат дома в MAX. Добавить должен тот, кто уже запускал бота, иначе бот сразу выйдет из чата.",
  "Бот напишет добавившему в личные сообщения. Сотруднику УК и председателю он предложит выбрать дом, другому жителю - прислать код привязки.",
  "Сделайте бота администратором чата и нажмите «Готово» в его сообщении.",
];

const Bound = ({ house }: { house: HouseCard }) => (
  <Card>
    <Flex align="center" gap={12}>
      <IconTile icon={checkIcon} tone="positive" />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {house.chat_title ?? "Чат без названия"}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Чат привязан: сюда бот присылает объявления УК для этого дома
        </Typography.Text>
      </Flex>
    </Flex>
  </Card>
);

const Unbound = ({ house }: { house: HouseCard }) => {
  const code = useCopy(2000);
  const rotation = useConfirm();

  const rotate = rqClient.useMutation(
    "post",
    "/api/admin/houses/{house_id}/binding-code",
    {
      onSuccess: async () => {
        rotation.dismiss();
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/admin/houses/{house_id}"],
        });
      },
    },
  );

  return (
    <Card>
      <Flex align="center" gap={12}>
        <IconTile icon={usersIcon} tone="neutral" />

        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={2}
        >
          <Typography.Text variant="body-strong" color="primary">
            Чат не привязан
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Пока чата нет, объявления в чат дома не уходят
          </Typography.Text>
        </Flex>
      </Flex>

      <Flex align="center" gap={8} className={styles.CodeBox}>
        <Flex className={styles.Grow} direction="column" gapY={2}>
          <Typography.Text variant="description" color="secondary">
            Код привязки
          </Typography.Text>
          <span className={styles.Code}>{house.chat_binding_code}</span>
        </Flex>

        <IconButton
          size="small"
          variant="secondary"
          aria-label={code.copied ? "Код скопирован" : "Скопировать код"}
          onClick={() => void code.copy(house.chat_binding_code)}
        >
          <Icon src={code.copied ? checkIcon : copyIcon} size={20} />
        </IconButton>
      </Flex>

      {code.copied && (
        <Typography.Text variant="description" color="secondary">
          Код скопирован, отправьте его тому, кто добавит бота в чат
        </Typography.Text>
      )}

      <ol className={styles.Steps}>
        {STEPS.map((step) => (
          <Typography.Text key={step} asChild variant="body" color="primary">
            <li>{step}</li>
          </Typography.Text>
        ))}
      </ol>

      <Button
        size="medium"
        variant="secondary"
        onClick={() => {
          rotate.reset();
          rotation.ask();
        }}
      >
        Выпустить новый код
      </Button>

      <ConfirmDialog
        isOpen={rotation.isOpen}
        title="Выпустить новый код?"
        description={`Код ${house.chat_binding_code} перестанет работать. Если вы уже отправили его жителю, отправьте новый.`}
        confirmLabel="Выпустить новый код"
        isPending={rotate.isPending}
        error={
          rotate.isError &&
          "Не получилось выпустить код. Проверьте связь и попробуйте ещё раз"
        }
        onConfirm={() =>
          rotate.mutate({
            params: { ...orgParams(), path: { house_id: house.id } },
          })
        }
        onClose={() => {
          if (!rotate.isPending) {
            rotation.dismiss();
          }
        }}
      />
    </Card>
  );
};

export const ChatSection = ({ house }: { house: HouseCard }) => (
  <Flex asChild align="stretch" direction="column" gap={8}>
    <section>
      <Typography.Text asChild variant="title" color="primary">
        <h2 className={styles.Title}>Чат дома</h2>
      </Typography.Text>

      {house.chat_bound ? <Bound house={house} /> : <Unbound house={house} />}
    </section>
  </Flex>
);
