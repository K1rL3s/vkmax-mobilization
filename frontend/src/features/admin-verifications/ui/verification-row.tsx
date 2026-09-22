import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { duration, formatDay } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";

import type { VerificationRequest } from "../model/use-verification-list";

import styles from "./verification-row.module.css";

const STATUS: Record<
  VerificationRequest["status"],
  { label: string; tone: "waiting" | "approved" | "rejected" }
> = {
  pending: { label: "Ждёт решения", tone: "waiting" },
  approved: { label: "Подтверждён", tone: "approved" },
  rejected: { label: "Отклонён", tone: "rejected" },
};

const when = (request: VerificationRequest) =>
  request.status === "pending"
    ? `ждёт ${duration(Date.now() - new Date(request.created_at).getTime())}`
    : formatDay(request.created_at);

type VerificationRowProps = {
  request: VerificationRequest;
  showAddress: boolean;
  search: string;
};

export const VerificationRow = ({
  request,
  showAddress,
  search,
}: VerificationRowProps) => {
  const navigate = useNavigate();
  const status = STATUS[request.status];

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate({
          pathname: generatePath(Routes.ADMIN_VERIFICATION, {
            verificationId: String(request.id),
          }),
          search,
        })
      }
    >
      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Flex align="center" gap={8}>
          <Typography.Text
            className={cn(styles.Grow, styles.Ellipsis)}
            variant="body-strong"
            color="primary"
          >
            {request.user_name}
          </Typography.Text>

          <Typography.Text
            className={cn(styles.StatusPill, styles[status.tone])}
            variant="label-strong"
          >
            {status.label}
          </Typography.Text>
        </Flex>

        <Flex align="center" gap={8}>
          {showAddress && (
            <Typography.Text
              className={cn(styles.Grow, styles.Ellipsis)}
              variant="description"
              color="secondary"
            >
              {request.address}
            </Typography.Text>
          )}

          <Typography.Text
            className={styles.Fixed}
            variant="description"
            color="secondary"
          >
            {when(request)}
          </Typography.Text>
        </Flex>
      </Flex>

      <Chevron />
    </Tappable>
  );
};
