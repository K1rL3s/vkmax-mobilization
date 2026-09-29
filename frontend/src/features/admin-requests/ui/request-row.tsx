import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import { STATUS_TONE, statusLabel } from "@/features/request";
import { cn } from "@/shared/lib/css";
import { formatDayTime, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { StatusPill } from "@/shared/ui/status-pill";

import { escalationNote, overdueNote } from "../domain/request-filters";
import {
  CHANNEL_LABEL,
  type AdminRequestItem,
} from "../domain/request-workflow";

import styles from "./request-row.module.css";

export const RequestRow = ({
  request,
  member,
}: {
  request: AdminRequestItem;
  member?: boolean;
}) => {
  const navigate = useNavigate();
  const grouped = !member && request.group_id != null;
  const overdue = overdueNote(request);
  const escalation = escalationNote(request, grouped);
  const flat = request.flat_number;
  const title = member
    ? (request.author_name ?? request.caller_name ?? "Звонок в УК")
    : request.category_label;
  const memberSubtitle = flat ? `Квартира ${flat}` : "Квартира не указана";
  const address = `№${request.id} · ${request.address}${!grouped && flat ? ` · кв. ${flat}` : ""}`;
  const meta = [
    grouped &&
      `Коллективная · ${request.group_size} ${plural(request.group_size, [
        "квартира",
        "квартиры",
        "квартир",
      ])}`,
    request.executor_name,
    request.channel === "miniapp" ? null : CHANNEL_LABEL[request.channel],
  ]
    .filter(Boolean)
    .join(" · ");
  const to = grouped
    ? generatePath(Routes.ADMIN_REQUEST_GROUP, {
        groupId: String(request.group_id),
      })
    : generatePath(Routes.ADMIN_REQUEST, { requestId: String(request.id) });

  return (
    <Tappable className={styles.Row} onClick={() => void navigate(to)}>
      <Flex
        className={styles.Content}
        align="stretch"
        direction="column"
        gap={4}
      >
        <Flex align="center" gap={8}>
          <Typography.Text
            className={cn(styles.Title, styles.Ellipsis)}
            variant="body-strong"
            color="primary"
          >
            {title}
          </Typography.Text>
          <StatusPill tone={STATUS_TONE[request.status]}>
            {statusLabel(request, "staff")}
          </StatusPill>
        </Flex>
        {escalation && (
          <Flex>
            <StatusPill tone="negative">{escalation}</StatusPill>
          </Flex>
        )}
        <Typography.Text
          className={styles.Ellipsis}
          variant="description"
          color="primary"
        >
          {request.description}
        </Typography.Text>
        <Typography.Text
          className={styles.Ellipsis}
          variant="description"
          color="secondary"
        >
          {member ? `№${request.id} · ${memberSubtitle}` : address}
        </Typography.Text>
        <Typography.Text
          className={cn(styles.Ellipsis, overdue && styles.Overdue)}
          variant="description"
          color={overdue ? undefined : "secondary"}
        >
          {overdue ?? (meta || `Подана ${formatDayTime(request.created_at)}`)}
        </Typography.Text>
      </Flex>
      <Chevron />
    </Tappable>
  );
};
