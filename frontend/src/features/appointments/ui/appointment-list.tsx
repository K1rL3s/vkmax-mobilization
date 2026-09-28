import { CellSimple } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { clockIcon } from "@/shared/ui/icon";
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
};

export const AppointmentList = ({ items, schedule }: AppointmentListProps) => (
  <div className={styles.Panel}>
    {items.map((item, index) => (
      <CellSimple
        key={item.id}
        separator={index > 0}
        before={<IconTile icon={clockIcon} tone="themed" />}
        title={schedule.appointmentTitle(item.starts_at)}
        subtitle={appointmentSubject(item)}
        showChevron
        asChild
      >
        <Link
          to={generatePath(Routes.APPOINTMENT, {
            appointmentId: String(item.id),
          })}
        />
      </CellSimple>
    ))}
  </div>
);
