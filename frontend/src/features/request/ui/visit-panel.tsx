import { Button, Typography } from "@maxhub/max-ui";

import type { RequestCard } from "../domain/types";
import type { Visit } from "../domain/visit";
import { useVisitPick } from "../model/use-visit-pick";

import styles from "./visit-panel.module.css";

export const VisitPanel = ({
  request,
  visit,
}: {
  request: RequestCard;
  visit: Visit;
}) => {
  const model = useVisitPick(request, visit);

  return (
    <section className={styles.Panel}>
      <div className={styles.Head}>
        <Typography.Text asChild variant="body-strong" color="primary">
          <h2>{model.title}</h2>
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {model.hint}
        </Typography.Text>
      </div>

      {model.windows.length > 0 && (
        <div className={styles.Grid}>
          {model.windows.map((window) => (
            <Button
              key={window.id}
              size="medium"
              className={styles.Window}
              variant={window.isPicked ? "primary" : "secondary"}
              disabled={model.isPicking}
              loading={window.isPending}
              aria-pressed={window.isPicked}
              onClick={() => model.pick(window.id)}
            >
              {window.label}
            </Button>
          ))}
        </div>
      )}

      {model.windows.length > 0 && (
        <Button
          size="medium"
          variant="ghost"
          stretched
          disabled={model.isPicking}
          loading={model.isDeclining}
          onClick={model.decline}
        >
          Ни одно время не подходит
        </Button>
      )}

      {model.error && (
        <Typography.Text variant="description" className={styles.Error}>
          {model.error}
        </Typography.Text>
      )}
    </section>
  );
};
