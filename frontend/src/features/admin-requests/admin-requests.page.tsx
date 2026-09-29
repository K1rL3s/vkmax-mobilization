import { Button, Flex, IconButton, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { FilterChip } from "@/shared/ui/filter-chip";
import { geoPinIcon, Icon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { FILTERS } from "./domain/request-filters";
import { useAdminRequestList } from "./model/use-admin-request-list";
import { FilterBar } from "./ui/filter-bar";
import { NoOrgAccess } from "./ui/no-org-access";
import { RequestRow } from "./ui/request-row";

import styles from "./admin-requests.module.css";

const AdminRequestsPage = () => {
  const list = useAdminRequestList();

  if (list.isForbidden) return <NoOrgAccess />;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gap={12}>
        <Flex align="center" justify="space-between" gap={12}>
          <Typography.Text asChild variant="header" color="primary">
            <h1>Заявки</h1>
          </Typography.Text>
          <IconButton asChild size="small" variant="secondary">
            <Link to={Routes.ADMIN_HOUSES} aria-label="Дома на карте">
              <Icon src={geoPinIcon} size={20} />
            </Link>
          </IconButton>
        </Flex>
        <Button asChild stretched>
          <Link to={Routes.ADMIN_REQUEST_PHONE}>Заявка по звонку</Link>
        </Button>
      </Flex>

      <Flex align="stretch" direction="column" gap={8}>
        {list.filters.house && (
          <FilterChip onRemove={() => list.updateFilter("house", "all")}>
            Дом: {list.houseAddress ?? "выбран на карте"}
          </FilterChip>
        )}
        <FilterBar
          groups={[
            {
              name: "filter",
              label: "Статус",
              options: FILTERS,
              value: list.filters.filter,
            },
            {
              name: "category",
              label: "Категория",
              options: [
                { id: "all", label: "Все" },
                ...list.categories.map(({ category, label }) => ({
                  id: category,
                  label,
                })),
              ],
              value: list.filters.category ?? "all",
            },
            {
              name: "place",
              label: "Место",
              options: [
                { id: "all", label: "Все" },
                { id: "flat", label: "Личные" },
                { id: "house", label: "Общие" },
              ],
              value: list.filters.place ?? "all",
            },
          ]}
          onChange={list.updateFilter}
          onReset={list.hasFilters ? list.clearFilters : undefined}
        />
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
