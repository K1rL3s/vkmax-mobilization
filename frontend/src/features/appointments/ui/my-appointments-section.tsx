import { Flex, Typography } from "@maxhub/max-ui";

import { ErrorState, LoadingState } from "@/shared/ui/state";

import { createSchedule } from "../domain/schedule";
import { useMyAppointments } from "../model/use-my-appointments";
import { AppointmentList } from "./appointment-list";

type MyAppointmentsSectionProps = {
  timeZone: string;
};

export const MyAppointmentsSection = ({
  timeZone,
}: MyAppointmentsSectionProps) => {
  const mine = useMyAppointments();

  if (mine.isPending) {
    return <LoadingState title="Загружаем ваши записи" />;
  }

  if (mine.isError) {
    return (
      <ErrorState
        error={mine.loadError}
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

      <AppointmentList items={mine.items} schedule={createSchedule(timeZone)} />
    </Flex>
  );
};
