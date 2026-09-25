import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useLocation, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { duration, formatDay } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  STATUS,
  type VerificationRequest,
} from "../model/use-verification-list";

import styles from "./verification-row.module.css";

const when = (request: VerificationRequest) =>
  request.status === "pending"
    ? `ждёт ${duration(Date.now() - new Date(request.created_at).getTime())}`
    : formatDay(request.created_at);

type VerificationRowProps = {
  request: VerificationRequest;
  showAddress: boolean;
};

export const VerificationRow = ({
  request,
  showAddress,
}: VerificationRowProps) => {
  const navigate = useNavigate();
  const { search } = useLocation();
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

          <StatusPill tone={status.tone}>{status.label}</StatusPill>
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
