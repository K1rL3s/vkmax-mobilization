import { Button, CellSimple, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";
import { z } from "zod";

import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import {
  buildingIcon,
  clockIcon,
  geoPinIcon,
  Icon,
  phoneIcon,
  wrenchIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  appointmentLabel,
  appointmentState,
  appointmentTone,
} from "./domain/schedule";
import { useAppointment } from "./model/use-appointment";

import styles from "./appointment.module.css";

const paramsSchema = z.object({
  appointmentId: z.coerce.number().int().positive(),
});

const AppointmentPage = () => {
  const params = useRouteParams(paramsSchema);
  const {
    appointment,
    org,
    schedule,
    isPending,
    isError,
    loadError,
    retry,
    isOpen,
    ask,
    dismiss,
    isCancelling,
    isFailed,
    confirm,
  } = useAppointment(params?.appointmentId ?? 0);

  if (isPending) {
    return <LoadingState fill title="Загружаем запись" />;
  }

  if (isError) {
    return <ErrorState error={loadError} fill onRetry={retry} />;
  }

  if (!appointment) {
    return (
      <EmptyState
        fill
        icon={clockIcon}
        title="Запись не найдена"
        description="Среди ваших записей такой нет. Часы приёма и ваши записи - в карточке дома"
        action={
          <Button asChild size="medium" variant="secondary">
            <Link to={Routes.APPOINTMENTS}>Записаться на приём</Link>
          </Button>
        }
      />
    );
  }

  const state = appointmentState(appointment);
  const tone = appointmentTone(state);

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex align="center" gap={12} className={styles.Summary}>
          <IconTile icon={clockIcon} tone={tone} size="large" />
          <Flex
            direction="column"
            align="flex-start"
            gapY={4}
            className={styles.Grow}
          >
            <Typography.Text asChild variant="title" color="primary">
              <h1>{schedule.appointmentTitle(appointment.starts_at)}</h1>
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {appointment.address}
            </Typography.Text>
            <StatusPill tone={tone}>{appointmentLabel(state)}</StatusPill>
          </Flex>
        </Flex>

        <div className={styles.Panel}>
          {org && (
            <CellSimple
              before={<Icon src={buildingIcon} className={styles.CellIcon} />}
              overline="Управляющая компания"
              title={org.name}
            />
          )}
          <CellSimple
            separator={org !== null}
            before={<Icon src={geoPinIcon} className={styles.CellIcon} />}
            overline="Где принимают"
            title={appointment.org_address}
          />
          <CellSimple
            separator
            before={<Icon src={phoneIcon} className={styles.CellIcon} />}
            overline="Телефон"
            title={appointment.org_phone}
            showChevron
            asChild
          >
            <a href={`tel:${appointment.org_phone}`} />
          </CellSimple>
          {appointment.request_id != null && (
            <CellSimple
              separator
              before={<Icon src={wrenchIcon} className={styles.CellIcon} />}
              overline="Обсудим"
              title={`Заявка №${appointment.request_id}`}
              showChevron
              asChild
            >
              <Link
                to={generatePath(Routes.REQUEST, {
                  requestId: String(appointment.request_id),
                })}
              />
            </CellSimple>
          )}
          <CellSimple
            separator
            before={<Icon src={clockIcon} className={styles.CellIcon} />}
            overline="Записались"
            title={`${schedule.slotDate(appointment.created_at)}, ${schedule.slotTime(appointment.created_at)}`}
          />
        </div>

        {state === "upcoming" && (
          <Typography.Text variant="description" color="tertiary">
            {schedule.bookedAhead(appointment) &&
              "Бот напоминает о записи накануне вечером. "}
            Чтобы прийти в другое время, отмените эту запись и выберите новый
            слот - он освободится для других жителей сразу
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        {state === "upcoming" ? (
          <Button size="large" stretched variant="secondary" onClick={ask}>
            Отменить запись
          </Button>
        ) : (
          <Button asChild size="large" stretched variant="secondary">
            <Link to={Routes.APPOINTMENTS}>Записаться на приём</Link>
          </Button>
        )}
      </div>

      <ConfirmDialog
        isOpen={isOpen}
        title="Отменить запись?"
        description={`Приём ${schedule.appointmentTitle(appointment.starts_at)} освободится для других жителей`}
        confirmLabel="Отменить запись"
        error={
          isFailed &&
          "Не получилось отменить запись. Проверьте связь и попробуйте ещё раз"
        }
        isPending={isCancelling}
        onConfirm={confirm}
        onClose={dismiss}
      />
    </Panel>
  );
};

export const Component = AppointmentPage;
