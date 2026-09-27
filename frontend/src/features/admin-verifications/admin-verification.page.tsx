import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { duration, formatDayTime } from "@/shared/lib/format";
import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";
import { usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useVerificationDecision } from "./model/use-verification-decision";
import {
  STATUS,
  useVerificationRequest,
  type VerificationRequest,
} from "./model/use-verification-list";
import { RejectDialog } from "./ui/reject-dialog";

import styles from "./admin-verification.module.css";

const sentAt = (request: VerificationRequest) => {
  const at = formatDayTime(request.created_at);

  return request.status === "pending"
    ? `${at} · ждёт ${duration(Date.now() - new Date(request.created_at).getTime())}`
    : at;
};

const Field = ({ label, value }: { label: string; value: string }) => (
  <Flex align="stretch" direction="column" gapY={2}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>

    <Typography.Text variant="body" color="primary">
      {value}
    </Typography.Text>
  </Flex>
);

const AdminVerificationPage = () => {
  const navigate = useNavigate();
  const { search } = useLocation();
  const params = useRouteParams(
    z.object({ verificationId: z.coerce.number().int().positive() }),
  );

  const { request, isPending, isError, loadError, retry } =
    useVerificationRequest(params?.verificationId ?? null);

  const decision = useVerificationDecision(
    request,
    () =>
      void navigate(
        { pathname: Routes.ADMIN_VERIFICATIONS, search },
        { replace: true },
      ),
  );

  if (isPending) {
    return <LoadingState fill title="Загружаем запрос" />;
  }

  if (isError) {
    return <ErrorState fill error={loadError} onRetry={retry} />;
  }

  if (!request) {
    return (
      <EmptyState
        fill
        icon={usersIcon}
        title="Запрос не найден"
        description="Возможно, его уже разобрал коллега, а очередь с тех пор перечитана."
      />
    );
  }

  const status = STATUS[request.status];
  const isWaiting = request.status === "pending";

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex align="stretch" direction="column" gapY={6}>
          <Flex align="center" gap={8}>
            <Typography.Text
              asChild
              className={styles.Grow}
              variant="header"
              color="primary"
            >
              <h1 className={styles.Title}>Квартира {request.flat_number}</h1>
            </Typography.Text>

            <StatusPill tone={status.tone}>{status.label}</StatusPill>
          </Flex>

          <Typography.Text variant="body" color="secondary">
            {request.address}
          </Typography.Text>
        </Flex>

        <div className={styles.Card}>
          <Field label="Житель" value={request.user_name} />

          <Field label="Назвал лицевой счёт" value={request.account_no} />

          <Field label="Запрос отправлен" value={sentAt(request)} />
        </div>

        {request.comment && (
          <Note title="Комментарий жителя" text={request.comment} />
        )}

        {request.status === "rejected" && request.reason && (
          <Note title="Причина отказа" text={request.reason} />
        )}

        {!isWaiting && (
          <Typography.Text variant="description" color="secondary">
            Запрос уже разобран, решение по нему больше не принимается.
          </Typography.Text>
        )}

        {decision.approveError && (
          <Typography.Text className={styles.Error} variant="description">
            {decision.approveError}
          </Typography.Text>
        )}
      </div>

      {isWaiting && (
        <div className={styles.Footer}>
          <Button
            size="large"
            stretched
            loading={decision.isApproving}
            onClick={decision.approve}
          >
            Подтвердить квартиру
          </Button>

          <Button
            size="large"
            stretched
            variant="secondary"
            disabled={decision.isApproving}
            onClick={decision.askReject}
          >
            Отклонить
          </Button>
        </div>
      )}

      {decision.rejectTarget && (
        <RejectDialog
          request={decision.rejectTarget}
          isPending={decision.isRejecting}
          error={decision.rejectError}
          onSubmit={decision.submitReject}
          onClose={decision.dismissReject}
        />
      )}
    </Panel>
  );
};

const Note = ({ title, text }: { title: string; text: string }) => (
  <Flex asChild align="stretch" direction="column" gapY={8}>
    <section>
      <Typography.Text asChild variant="title" color="primary">
        <h2 className={styles.Title}>{title}</h2>
      </Typography.Text>

      <Typography.Text className={styles.Card} variant="body" color="primary">
        {text}
      </Typography.Text>
    </section>
  </Flex>
);

export const Component = AdminVerificationPage;
