import { Flex, Typography } from "@maxhub/max-ui";

import { STATUS_LABEL, type RequestListItem } from "@/features/request";
import { cn } from "@/shared/lib/css";

import styles from "./request-choice.module.css";

type RequestChoiceProps = {
  requests: RequestListItem[];
  value: number | null;
  onChange: (requestId: number | null) => void;
};

export const RequestChoice = ({
  requests,
  value,
  onChange,
}: RequestChoiceProps) => {
  const options = [
    { id: null, title: "Без заявки", subtitle: "Общий вопрос к УК" },
    ...requests.map((request) => ({
      id: request.id,
      title: `№${request.id} · ${request.description}`,
      subtitle: STATUS_LABEL[request.status],
    })),
  ];

  return (
    <div className={styles.Panel}>
      {options.map((option) => (
        <label key={option.id ?? "none"} className={styles.Option}>
          <input
            className={styles.Control}
            type="radio"
            name="appointment-request"
            checked={option.id === value}
            onChange={() => onChange(option.id)}
          />

          <Flex
            direction="column"
            align="stretch"
            gapY={2}
            className={styles.Grow}
          >
            <Typography.Text
              variant="body"
              color="primary"
              className={styles.Title}
            >
              {option.title}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {option.subtitle}
            </Typography.Text>
          </Flex>

          <span
            className={cn(styles.Marker, option.id === value && styles.checked)}
          />
        </label>
      ))}
    </div>
  );
};
