import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useBoolean, useCopy } from "@siberiacancode/reactuse";

import type { Letter } from "../domain/letters";

import styles from "./letter-panel.module.css";

export const LetterPanel = ({ title, hint, text, estimate }: Letter) => {
  const [open, toggle] = useBoolean();
  const copy = useCopy(2000);

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {title}
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {hint}
        </Typography.Text>
      </Flex>

      {estimate && (
        <Flex align="stretch" direction="column" gapY={2}>
          <Typography.Text variant="body-strong" color="primary">
            ≈ {estimate} к перерасчёту
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Оценка по ПП 354, прил. 1, не юридическая консультация
          </Typography.Text>
        </Flex>
      )}

      {open && (
        <>
          <Typography.Text asChild variant="description" color="primary">
            <pre className={styles.Text}>{text}</pre>
          </Typography.Text>

          <Button
            size="medium"
            variant="primary"
            stretched
            onClick={() => void copy.copy(text)}
          >
            {copy.copied ? "Текст скопирован" : "Скопировать"}
          </Button>
        </>
      )}

      <Button
        size="medium"
        variant="secondary"
        stretched
        onClick={() => toggle()}
      >
        {open ? "Свернуть" : "Показать текст"}
      </Button>
    </div>
  );
};
