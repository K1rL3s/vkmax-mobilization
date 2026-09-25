import { CellSimple, IconButton } from "@maxhub/max-ui";

import { clockIcon, closeIcon, Icon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  appointmentSubject,
  type Appointment,
  type Schedule,
} from "../domain/schedule";

import styles from "./appointment-list.module.css";

type AppointmentListProps = {
  items: Appointment[];
  schedule: Schedule;
  onCancel: (appointment: Appointment) => void;
};

export const AppointmentList = ({
  items,
  schedule,
  onCancel,
}: AppointmentListProps) => (
  <div className={styles.Panel}>
    {items.map((item, index) => (
      <CellSimple
        key={item.id}
        separator={index > 0}
        before={<IconTile icon={clockIcon} tone="themed" />}
        title={schedule.appointmentTitle(item.starts_at)}
        subtitle={appointmentSubject(item)}
        after={
          <IconButton
            size="xsmall"
            variant="ghost"
            aria-label={`Отменить запись на ${schedule.appointmentTitle(item.starts_at)}`}
            onClick={() => onCancel(item)}
          >
            <Icon src={closeIcon} size={18} className={styles.Close} />
          </IconButton>
        }
      />
    ))}
  </div>
);
