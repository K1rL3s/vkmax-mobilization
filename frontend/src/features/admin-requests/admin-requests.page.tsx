import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { FILTERS } from "./domain/request-filters";
import { useAdminRequestList } from "./model/use-admin-request-list";
import { ChipRow } from "./ui/chip-row";
import { NoOrgAccess } from "./ui/no-org-access";
import { RequestRow } from "./ui/request-row";

import styles from "./admin-requests.module.css";

const AdminRequestsPage = () => {
  const list = useAdminRequestList();

  if (list.isForbidden) return <NoOrgAccess />;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gap={12}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Заявки</h1>
        </Typography.Text>
        <Button asChild stretched>
          <Link to={Routes.ADMIN_REQUEST_PHONE}>Заявка по звонку</Link>
        </Button>
      </Flex>

      <Flex align="stretch" direction="column" gap={8}>
        <ChipRow
          label="Заявки"
          options={FILTERS}
          value={list.filters.filter}
          onChange={(id) => list.updateFilter("filter", id)}
        />
        {list.categories.length > 0 && (
          <ChipRow
            label="Категория"
            options={[
              { id: "all", label: "Все категории" },
              ...list.categories.map(({ category, label }) => ({
                id: category,
                label,
              })),
            ]}
            value={list.filters.category ?? "all"}
            onChange={(id) => list.updateFilter("category", id)}
          />
        )}
      </Flex>

      {list.isPending && <LoadingState fill title="Загружаем заявки…" />}
      {list.isError && (
        <ErrorState error={list.loadError} fill onRetry={list.retry} />
      )}

      {list.isSuccess && list.sections.length === 0 && (
        <EmptyState
          fill
          title={list.hasFilters ? "В этом фильтре пусто" : "Заявок пока нет"}
          description={
            list.hasFilters
              ? "Попробуйте другой фильтр или категорию."
              : "Здесь появятся обращения жителей. Входящий звонок можно записать кнопкой выше."
          }
          action={
            list.hasFilters && (
              <Button variant="secondary" onClick={list.clearFilters}>
                Показать все заявки
              </Button>
            )
          }
        />
      )}

      {list.sections.map((section) => (
        <Flex
          key={section.title}
          asChild
          align="stretch"
          direction="column"
          gap={8}
        >
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>{section.title}</h2>
            </Typography.Text>
            {section.items.map((request) => (
              <RequestRow key={request.id} request={request} />
            ))}
          </section>
        </Flex>
      ))}

      {list.isClipped && (
        <Typography.Text variant="description" color="secondary">
          Показаны последние 100 заявок из {list.total}. Чтобы увидеть
          остальные, сузьте фильтр.
        </Typography.Text>
      )}
    </Panel>
  );
};

export const Component = AdminRequestsPage;
