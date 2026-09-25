import { Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { checkIcon, Icon } from "@/shared/ui/icon";

import type { TimelineStep } from "../domain/timeline";

import styles from "./request-timeline.module.css";

export const RequestTimeline = ({ steps }: { steps: TimelineStep[] }) => (
  <div className={styles.Timeline}>
    {steps.map((step, index) => (
      <div key={step.status} className={cn(styles.Step, styles[step.state])}>
        <div className={styles.Rail}>
          <span className={styles.Dot}>
            {step.state === "done" && <Icon src={checkIcon} size={12} />}
          </span>
          {index < steps.length - 1 && <span className={styles.Line} />}
        </div>

        <div className={styles.Body}>
          <Typography.Text
            className={styles.Title}
            variant="body-strong"
            color="primary"
          >
            {step.title}
          </Typography.Text>
          {step.hint && (
            <Typography.Text variant="description" color="secondary">
              {step.hint}
            </Typography.Text>
          )}
        </div>
      </div>
    ))}
  </div>
);
