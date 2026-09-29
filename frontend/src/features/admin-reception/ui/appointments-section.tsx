import { useEffect, useRef, useState } from "react";
import { Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { formatTime } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { FilterChip } from "@/shared/ui/filter-chip";
import { StatusPill } from "@/shared/ui/status-pill";

import { dayKey, dayTitle, shiftDay } from "../domain/day";
import type { Appointment } from "../domain/schedule";
import { useOrgAppointments } from "../model/use-reception";

import styles from "./appointments-section.module.css";

const Row = ({ item }: { item: Appointment }) => {
  const isCancelled = item.status === "cancelled";

  const body = (
    <>
      <Typography.Text
        className={styles.Time}
        variant="title"
        color={isCancelled ? "secondary" : "primary"}
      >
        {formatTime(item.starts_at)}
      </Typography.Text>

      <Flex align="stretch" direction="column" gapY={2} className={styles.Grow}>
        <Typography.Text
          variant="body"
          color={isCancelled ? "secondary" : "primary"}
        >
          {item.user_name ?? "Житель"}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {[
            item.flat_number
              ? `кв. ${item.flat_number}`
              : "квартира не указана",
            item.request_id !== null && `заявка №${item.request_id}`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </Typography.Text>
      </Flex>

      {isCancelled ? (
        <StatusPill tone="neutral">отменена</StatusPill>
      ) : (
        item.request_id !== null && <Chevron />
      )}
    </>
  );

  return item.request_id !== null && !isCancelled ? (
    <Link
      className={cn(styles.Row, styles.link)}
      to={Routes.ADMIN_REQUEST.replace(":requestId", String(item.request_id))}
    >
      {body}
    </Link>
  ) : (
    <div className={cn(styles.Row, isCancelled && styles.cancelled)}>
      {body}
    </div>
  );
};

export const AppointmentsSection = () => {
  const [day, setDay] = useState(() => dayKey(new Date()));
  const { appointments, houseId, houseAddress, clearHouse } =
    useOrgAppointments(day);
  const section = useRef<HTMLElement>(null);
  const filtered = houseId !== undefined;

  useEffect(() => {
    if (filtered) section.current?.scrollIntoView();
  }, [filtered]);

  return (
    <section ref={section} className={styles.Section}>
      <Flex align="center" gap={8}>
        <Typography.Text
          asChild
          className={styles.Grow}
          variant="title"
          color="primary"
        >
          <h2>Записи на приём</h2>
        </Typography.Text>

        <button
          type="button"
          className={styles.Arrow}
          aria-label="Предыдущий день"
          onClick={() => setDay(shiftDay(day, -1))}
        >
          ‹
        </button>

        <button
          type="button"
          className={styles.Arrow}
          aria-label="Следующий день"
          onClick={() => setDay(shiftDay(day, 1))}
        >
          ›
        </button>
      </Flex>

      <Typography.Text variant="description" color="secondary">
        {dayTitle(day)}
      </Typography.Text>

      {filtered && (
        <FilterChip onRemove={clearHouse}>
          Дом: {houseAddress ?? "выбран на карте"}
        </FilterChip>
      )}

      {appointments.isPending ? (
        <LoadingState title="Загружаем записи" />
      ) : appointments.isError ? (
        <ErrorState
          error={appointments.error}
          description="Не получилось загрузить записи на приём"
          onRetry={() => void appointments.refetch()}
        />
      ) : appointments.data.length === 0 ? (
        <EmptyState
          title={
            filtered
              ? "Из этого дома в этот день никто не записан"
              : "В этот день никто не записан"
          }
          description="Жители записываются сами из своего кабинета - в кабинете УК записать человека нельзя. Проверьте соседние дни стрелками выше."
        />
      ) : (
        <div
          className={cn(
            styles.List,
            appointments.isPlaceholderData && styles.stale,
          )}
        >
          {appointments.data.map((item) => (
            <Row key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
};
