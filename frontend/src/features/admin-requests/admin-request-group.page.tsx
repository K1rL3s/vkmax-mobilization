import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { isForbidden } from "@/shared/api/errors";
import { plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useAdminRequestGroup } from "./model/use-admin-request";
import { NoOrgAccess } from "./ui/no-org-access";
import { RequestRow } from "./ui/request-row";
import { RequestStatusAction } from "./ui/request-status-action";

import styles from "./admin-requests.module.css";

const AdminRequestGroupPage = () => {
  const { valid, query } = useAdminRequestGroup();
  if (!valid)
    return (
      <EmptyState
        fill
        title="Неверный адрес коллективной заявки"
        description="Откройте коллективную заявку из списка."
        action={
          <Button asChild>
            <Link to={Routes.ADMIN_REQUESTS}>К заявкам</Link>
          </Button>
        }
      />
    );
  if (isForbidden(query.error)) return <NoOrgAccess />;
  if (query.isPending)
    return <LoadingState fill title="Загружаем коллективную заявку…" />;
  if (query.isError)
    return (
      <ErrorState
        error={query.error}
        fill
        onRetry={() => void query.refetch()}
      />
    );
  const group = query.data;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gap={6}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>Коллективная заявка</h1>
        </Typography.Text>
        <Typography.Text variant="body" color="secondary">
          {group.address}
        </Typography.Text>
        <Flex align="center" wrap="wrap" gap={8}>
          <StatusPill tone={group.status === "closed" ? "neutral" : "themed"}>
            {group.status === "closed" ? "Закрыта" : "Открыта"}
          </StatusPill>
          <StatusPill tone="neutral">{group.category_label}</StatusPill>
          <StatusPill tone="neutral">
            {group.flats_count}{" "}
            {plural(group.flats_count, ["квартира", "квартиры", "квартир"])}
          </StatusPill>
        </Flex>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Авторы и заявки · {group.requests.length}</h2>
          </Typography.Text>
          {group.requests.length === 0 ? (
            <EmptyState
              title="Участников пока нет"
              description="Здесь появятся заявки, присоединённые к коллективной."
            />
          ) : (
            group.requests.map((request) => (
              <RequestRow key={request.id} request={request} member />
            ))
          )}
        </section>
      </Flex>

      <RequestStatusAction target={{ kind: "group", group }} />
    </Panel>
  );
};

export const Component = AdminRequestGroupPage;
