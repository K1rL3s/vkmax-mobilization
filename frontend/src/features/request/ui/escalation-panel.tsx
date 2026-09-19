import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { useHouseCard } from "@/features/house";

import { gjiAppeal } from "../domain/gji";
import type { RequestCard } from "../domain/types";

import styles from "./escalation-panel.module.css";

export const EscalationPanel = ({ request }: { request: RequestCard }) => {
  const house = useHouseCard(request.house_id);
  const copy = useCopy(2000);

  if (!house.data) {
    return null;
  }

  const text = gjiAppeal(request, house.data);

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="title" color="primary">
          Можно обратиться в жилищную инспекцию
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Мы подготовили текст с данными заявки. Скопируйте и отправьте в ГЖИ,
          если посчитаете нужным
        </Typography.Text>
      </Flex>

      <Typography.Text asChild variant="description" color="primary">
        <pre className={styles.Appeal}>{text}</pre>
      </Typography.Text>

      <Button
        size="large"
        variant="secondary"
        stretched
        onClick={() => void copy.copy(text)}
      >
        {copy.copied ? "Текст скопирован" : "Скопировать текст"}
      </Button>
    </div>
  );
};
