import { Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import {
  boltIcon,
  buildingIcon,
  checkIcon,
  documentIcon,
  hardHatIcon,
  Icon,
  userIcon,
  wrenchIcon,
} from "@/shared/ui/icon";

import type { TimelineStep } from "../domain/timeline";
import type { RequestCategory, RequestStatus } from "../domain/types";

import zheka from "./zheka.webp";
import styles from "./request-timeline.module.css";

export const RequestTimeline = ({
  steps,
  category,
}: {
  steps: TimelineStep[];
  category: RequestCategory;
}) => (
  <div className={styles.Timeline}>
    {steps.map((step, index) => (
      <div key={step.status} className={cn(styles.Step, styles[step.state])}>
        <div className={styles.Rail}>
          {step.status === "done" && step.state === "done" ? (
            <img src={zheka} alt="" className={styles.Mascot} />
          ) : (
            <span className={styles.Dot}>
              <Icon
                src={
                  step.status === "in_progress"
                    ? (WORKER_ICON[category] ?? hardHatIcon)
                    : STEP_ICON[step.status]
                }
                size={18}
              />
            </span>
          )}
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

const STEP_ICON: Record<RequestStatus, string> = {
  new: documentIcon,
  accepted: buildingIcon,
  in_progress: hardHatIcon,
  on_review: userIcon,
  done: checkIcon,
};

const WORKER_ICON: Partial<Record<RequestCategory, string>> = {
  leak: wrenchIcon,
  water_supply: wrenchIcon,
  heating: wrenchIcon,
  electricity: boltIcon,
};
