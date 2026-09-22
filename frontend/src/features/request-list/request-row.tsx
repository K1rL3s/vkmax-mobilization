import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import {
  CATEGORY_ICON,
  deadlineLeft,
  isOnReview,
  STATUS_LABEL,
  STATUS_TONE,
  type RequestCompletionReason,
  type RequestListItem,
} from "@/features/request";
import { formatDay, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { IconTile } from "@/shared/ui/icon-tile";
import { StatusPill } from "@/shared/ui/status-pill";

import styles from "./request-row.module.css";

type Note = {
  text: string;
  tone: "muted" | "action" | "overdue";
};

// оценить можно только принятую работу: у отклонённой и автозакрытой заявки
// на карточке блока оценки нет, и звать туда жителя незачем
const CLOSED_NOTE: Record<RequestCompletionReason, Note> = {
  resident_accepted: { text: "Оцените работу", tone: "action" },
  resident_rejected: { text: "Вы не приняли работу", tone: "muted" },
  auto_closed: { text: "Закрыта автоматически", tone: "muted" },
};

// вторая строка карточки: пока заявка идёт - нормативный срок, дальше - то,
// чего лента ждёт от жителя
const note = (request: RequestListItem): Note | null => {
  if (isOnReview(request.status)) {
    return { text: "Проверьте работу", tone: "action" };
  }

  if (request.status === "done") {
    if (request.rating) {
      return { text: `Ваша оценка: ${request.rating} из 5`, tone: "muted" };
    }

    return request.completion_reason
      ? CLOSED_NOTE[request.completion_reason]
      : null;
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
          <StatusPill tone={tone}>{STATUS_LABEL[request.status]}</StatusPill>
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

      <Chevron />
    </Tappable>
  );
};
