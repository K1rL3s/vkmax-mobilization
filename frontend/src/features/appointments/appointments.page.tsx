import type { ReactNode } from "react";
import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import { buildingIcon, clockIcon, Icon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { closedDaysCaption, dayTitle, monthLabel } from "./domain/schedule";
import { useAccessRequests } from "./model/use-access-requests";
import { useBooking } from "./model/use-booking";
import { useMyAppointments } from "./model/use-my-appointments";
import { AccessRequestCard } from "./ui/access-request-card";
import { AppointmentList } from "./ui/appointment-list";
import { BookedResult } from "./ui/booked-result";
import { DayChips } from "./ui/day-chips";
import { RequestChoice } from "./ui/request-choice";
import { TimeGrid } from "./ui/time-grid";

import styles from "./appointments.module.css";

type SectionProps = {
  title: string;
  aside?: string;
  children: ReactNode;
};

const Section = ({ title, aside, children }: SectionProps) => (
  <Flex asChild direction="column" align="stretch" gap={12}>
    <section>
      <Flex align="baseline" gap={8}>
        <Typography.Text
          asChild
          variant="title"
          color="primary"
          className={styles.Grow}
        >
          <h2>{title}</h2>
        </Typography.Text>
        {aside && (
          <Typography.Text variant="description" color="tertiary">
            {aside}
          </Typography.Text>
        )}
      </Flex>
      {children}
    </section>
  </Flex>
);

const AppointmentsPage = () => {
  const booking = useBooking();
  const mine = useMyAppointments();
  const access = useAccessRequests();
  const residency = useSession().currentResidency;
  const parts = [booking, mine, access];

  if (parts.some((part) => part.isPending)) {
    return <LoadingState fill title="Загружаем расписание приёма" />;
  }

  if (parts.some((part) => part.isError)) {
    return (
      <ErrorState
        fill
        error={parts.find((part) => part.isError)?.loadError}
        onRetry={() => {
          for (const part of parts) {
            if (part.isError) {
              part.retry();
            }
          }
        }}
      />
    );
  }

  if (booking.booked) {
    return (
      <Panel className={styles.Page} mode="secondary">
        <BookedResult
          appointment={booking.booked}
          schedule={booking.schedule}
          orgName={booking.org?.name}
          request={booking.bookedRequest}
          onDone={booking.finish}
        />
      </Panel>
    );
  }

  const { org, day, slot, schedule } = booking;
  const today = schedule.dayKey(new Date());
  const accessRequests = access.items.filter((item) => item.date >= today);
  const closedDays = closedDaysCaption(booking.days);
  const halves = schedule.splitDay(day?.slots ?? []);

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        {org && (
          <Flex align="center" gap={12} className={styles.Org}>
            <Icon src={buildingIcon} size={24} className={styles.OrgIcon} />
            <Flex
              direction="column"
              align="stretch"
              gapY={2}
              className={styles.Grow}
            >
              <Typography.Text variant="body-strong" color="primary">
                {org.name}
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                {[org.address, org.reception_note].filter(Boolean).join(" · ")}
              </Typography.Text>
            </Flex>
          </Flex>
        )}

        {accessRequests.length > 0 && (
          <Section title="Доступ в квартиру">
            {accessRequests.map((request) => (
              <AccessRequestCard
                key={request.id}
                request={request}
                schedule={schedule}
                confirmPath={
                  residency &&
                  (!residency.verified || access.needsConfirmation(request.id))
                    ? generatePath(Routes.FLAT_CONFIRMATION, {
                        residentId: String(residency.resident_id),
                      })
                    : null
                }
                isPicking={access.isPicking}
                pendingSlotId={access.pendingSlotId}
                error={access.errorOf(request.id)}
                onPick={(slotId) => access.pick(request.id, slotId)}
              />
            ))}
          </Section>
        )}

        {day ? (
          <>
            <Section title="День" aside={monthLabel(day.date)}>
              <DayChips
                days={booking.days}
                value={day.key}
                onChange={booking.selectDay}
              />
              {closedDays && (
                <Typography.Text variant="description" color="tertiary">
                  {closedDays}
                </Typography.Text>
              )}
            </Section>

            <Section title="Время" aside={dayTitle(day.date)}>
              <TimeGrid
                groups={halves.groups}
                value={slot?.starts_at}
                schedule={schedule}
                isOwn={mine.isOwn}
                onChange={booking.selectSlot}
              />
              <Typography.Text variant="description" color="tertiary">
                {[
                  day.slots.some((item) => item.is_free && !mine.isOwn(item))
                    ? "Бледные слоты уже заняты"
                    : "На этот день всё время занято, выберите другой",
                  halves.lunch,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Typography.Text>
            </Section>

            {booking.openRequests.length > 0 && (
              <Section title="Обсудить заявку" aside="необязательно">
                <RequestChoice
                  requests={booking.openRequests}
                  value={booking.requestId}
                  onChange={booking.selectRequest}
                />
                <Typography.Text variant="description" color="tertiary">
                  Сотрудник УК заранее откроет заявку и подготовится к
                  разговору. Накануне вечером бот напомнит о записи
                </Typography.Text>
              </Section>
            )}

            <Flex direction="column" align="stretch" gap={8}>
              {booking.error && (
                <Typography.Text
                  variant="description"
                  className={styles.Failed}
                >
                  {booking.error}
                </Typography.Text>
              )}
              <Button
                size="large"
                stretched
                disabled={!slot}
                loading={booking.isSending}
                onClick={booking.send}
              >
                {slot
                  ? `Записаться на ${schedule.slotDate(slot.starts_at)}, ${schedule.slotTime(slot.starts_at)}`
                  : "Выберите время"}
              </Button>
            </Flex>
          </>
        ) : (
          <EmptyState
            icon={clockIcon}
            title="Онлайн-запись не настроена"
            description={
              org
                ? [
                    `У ${org.name} запись на приём через приложение пока не открыта.`,
                    org.phone &&
                      `Часы приёма можно уточнить по телефону ${org.phone.replaceAll(" ", "\u00a0")}`,
                  ]
                    .filter(Boolean)
                    .join(" ")
                : "У дома нет управляющей компании в сервисе, записаться на приём пока не к кому"
            }
            action={
              org?.phone && (
                <Button asChild size="medium" variant="secondary">
                  <a href={`tel:${org.phone}`}>Позвонить в УК</a>
                </Button>
              )
            }
          />
        )}

        <Section title="Мои записи">
          {mine.items.length > 0 ? (
            <AppointmentList items={mine.items} schedule={schedule} />
          ) : (
            <Typography.Text variant="description" color="tertiary">
              {day
                ? "Предстоящих записей нет. Выберите день и время выше"
                : "Предстоящих записей нет"}
            </Typography.Text>
          )}
        </Section>
      </div>
    </Panel>
  );
};

export const Component = AppointmentsPage;
