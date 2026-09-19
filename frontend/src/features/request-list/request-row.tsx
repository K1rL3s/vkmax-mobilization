import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import {
  CATEGORY_ICON,
  deadlineLeft,
  formatDay,
  plural,
  STATUS_LABEL,
  STATUS_TONE,
  type RequestListItem,
} from "@/features/request";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { chevronSmallIcon, Icon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./request-row.module.css";

type Note = {
  text: string;
  tone: "muted" | "action" | "overdue";
};

// вторая строка карточки: пока заявка идёт - нормативный срок, дальше - то,
// чего лента ждёт от жителя
const note = (request: RequestListItem): Note | null => {
  if (request.status === "on_review") {
    return { text: "Проверьте работу", tone: "action" };
  }

  if (request.status === "done") {
    return request.rating
      ? { text: `Ваша оценка: ${request.rating} из 5`, tone: "muted" }
      : { text: "Оцените работу", tone: "action" };
  }

  const deadline = deadlineLeft(request.deadline_at);
  const flats =
    request.group_size > 1
      ? `${request.group_size} ${plural(request.group_size, ["квартира", "квартиры", "квартир"])}`
      : null;
  const text = [deadline?.text, flats].filter(Boolean).join(" · ");

  return text ? { text, tone: deadline?.overdue ? "overdue" : "muted" } : null;
};

export const RequestRow = ({ request }: { request: RequestListItem }) => {
  const navigate = useNavigate();
  const line = note(request);
  const tone = STATUS_TONE[request.status];

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate(
          generatePath(Routes.REQUEST, { requestId: String(request.id) }),
        )
      }
    >
      <IconTile icon={CATEGORY_ICON[request.category]} tone={tone} />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Flex align="center" gap={8}>
          <Typography.Text
            className={styles.Grow}
            variant="description"
            color="secondary"
          >
            №{request.id} · {formatDay(request.created_at)}
          </Typography.Text>
          <Typography.Text
            className={cn(styles.StatusPill, styles[tone])}
            variant="label-strong"
          >
            {STATUS_LABEL[request.status]}
          </Typography.Text>
        </Flex>

        <Typography.Text
          className={styles.Ellipsis}
          variant="body-strong"
          color="primary"
        >
          {request.description}
        </Typography.Text>

        {line && (
          <Typography.Text className={styles[line.tone]} variant="description">
            {line.text}
          </Typography.Text>
        )}
      </Flex>

      <Icon src={chevronSmallIcon} size={12} className={styles.Chevron} />
    </Tappable>
  );
};
