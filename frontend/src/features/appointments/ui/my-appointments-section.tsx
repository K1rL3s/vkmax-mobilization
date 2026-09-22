import { CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { clockIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { createSchedule } from "../domain/schedule";
import { useMyAppointments } from "../model/use-my-appointments";

import styles from "./my-appointments-section.module.css";

type MyAppointmentsSectionProps = {
  timeZone: string;
};

// без записей секции нет: кнопка записи над ней уже говорит, что делать
export const MyAppointmentsSection = ({
  timeZone,
}: MyAppointmentsSectionProps) => {
  const mine = useMyAppointments();
  const schedule = createSchedule(timeZone);

  if (mine.isPending) {
    return <LoadingState title="Загружаем ваши записи" />;
  }

  if (mine.isError) {
    return (
      <ErrorState
        description="Не получилось загрузить ваши записи на приём"
        onRetry={mine.retry}
      />
    );
  }

  if (mine.items.length === 0) {
    return null;
  }

  return (
    <Flex direction="column" align="stretch" gap={8}>
      <Typography.Text variant="description" color="secondary">
        Мои записи
      </Typography.Text>

      <div className={styles.Panel}>
        {mine.items.map((item, index) => (
          <CellSimple
            key={item.id}
            separator={index > 0}
            before={<IconTile icon={clockIcon} tone="themed" />}
            title={schedule.appointmentTitle(item.starts_at)}
            subtitle={
              item.request_id
                ? `Обсудить заявку №${item.request_id} · офис УК`
                : "Общий вопрос · офис УК"
            }
            showChevron
            asChild
          >
            <Link to={Routes.APPOINTMENTS} />
          </CellSimple>
        ))}
      </div>
    </Flex>
  );
};
