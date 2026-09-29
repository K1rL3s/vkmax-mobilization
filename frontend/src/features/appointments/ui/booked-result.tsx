import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { RequestListItem } from "@/features/request";
import {
  buildingIcon,
  checkIcon,
  homeIcon,
  Icon,
  wrenchIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import type { Appointment, Schedule } from "../domain/schedule";

import styles from "./booked-result.module.css";

type BookedResultProps = {
  appointment: Appointment;
  schedule: Schedule;
  orgName: string | undefined;
  request: RequestListItem | undefined;
  onDone: () => void;
};

export const BookedResult = ({
  appointment,
  schedule,
  orgName,
  request,
  onDone,
}: BookedResultProps) => {
  const rows = [
    orgName && {
      icon: buildingIcon,
      label: "Управляющая компания",
      value: orgName,
    },
    { icon: homeIcon, label: "Где", value: appointment.org_address },
    appointment.request_id && {
      icon: wrenchIcon,
      label: "Обсудим",
      value: request
        ? `Заявка №${request.id} · ${request.description}`
        : `Заявка №${appointment.request_id}`,
    },
  ].filter((row) => !!row);

  return (
    <>
      <div className={styles.Content}>
        <Flex
          direction="column"
          align="center"
          gap={12}
          className={styles.Hero}
        >
          <IconTile
            icon={checkIcon}
            tone="positive"
            size="xlarge"
            className={styles.Check}
          />
          <Typography.Text asChild variant="header" color="primary">
            <h1 className={styles.Title}>Вы записаны на приём</h1>
          </Typography.Text>
          <Typography.Text variant="detail" color="secondary">
            {schedule.appointmentTitle(appointment.starts_at)}
          </Typography.Text>
        </Flex>

        <Flex
          direction="column"
          align="stretch"
          gap={16}
          className={styles.Panel}
        >
          {rows.map((row) => (
            <Flex key={row.label} align="center" gap={12}>
              <Icon src={row.icon} size={24} className={styles.Icon} />
              <Flex
                direction="column"
                align="stretch"
                gapY={2}
                className={styles.Grow}
              >
                <Typography.Text variant="description" color="secondary">
                  {row.label}
                </Typography.Text>
                <Typography.Text variant="detail" color="primary">
                  {row.value}
                </Typography.Text>
              </Flex>
            </Flex>
          ))}
        </Flex>

        <Typography.Text
          variant="description"
          color="tertiary"
          className={styles.Note}
        >
          {schedule.bookedAhead(appointment) &&
            "Накануне вечером бот напомнит о записи. "}
          Она уже есть в разделе «Мои записи», там же её можно отменить
        </Typography.Text>
      </div>

      <div className={styles.Footer}>
        <Button size="large" stretched onClick={onDone}>
          Готово
        </Button>
      </div>
    </>
  );
};
