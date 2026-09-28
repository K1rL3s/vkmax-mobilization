import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useBoolean, useCopy } from "@siberiacancode/reactuse";

import type { Letter } from "../domain/letters";

import styles from "./letter-panel.module.css";

export const LetterPanel = ({ title, hint, text }: Letter) => {
  const [open, toggle] = useBoolean();
  const copy = useCopy(2000);

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="title" color="primary">
          {title}
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {hint}
        </Typography.Text>
      </Flex>

      {open && (
        <>
          <Typography.Text asChild variant="description" color="primary">
            <pre className={styles.Text}>{text}</pre>
          </Typography.Text>

          <Button
            size="large"
            variant="primary"
            stretched
            onClick={() => void copy.copy(text)}
          >
            {copy.copied ? "Текст скопирован" : "Скопировать"}
          </Button>
        </>
      )}

      <Button
        size="large"
        variant="secondary"
        stretched
        onClick={() => toggle()}
      >
        {open ? "Свернуть" : "Показать текст"}
      </Button>
    </div>
  );
};
