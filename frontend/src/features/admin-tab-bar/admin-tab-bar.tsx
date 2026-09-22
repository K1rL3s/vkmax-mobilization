import { Typography } from "@maxhub/max-ui";
import { NavLink } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import {
  buildingIcon,
  chartIcon,
  Icon,
  megaphoneIcon,
  navMeetingsIcon,
  navRequestsIcon,
  pollIcon,
} from "@/shared/ui/icon";

import styles from "./admin-tab-bar.module.css";

const TABS = [
  { to: Routes.ADMIN_REQUESTS, label: "Заявки", icon: navRequestsIcon },
  { to: Routes.ADMIN_ANNOUNCEMENTS, label: "Объявления", icon: megaphoneIcon },
  { to: Routes.ADMIN_POLLS, label: "Опросы", icon: pollIcon },
  { to: Routes.ADMIN_RECEPTION, label: "Приём", icon: navMeetingsIcon },
  { to: Routes.ADMIN_HOUSES, label: "Дома", icon: buildingIcon },
  { to: Routes.ADMIN_ANALYTICS, label: "Аналитика", icon: chartIcon },
];

export const AdminTabBar = () => {
  return (
    <nav className={styles.AdminTabBar}>
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            cn(styles.Tab, isActive && styles.TabActive)
          }
        >
          <Icon src={tab.icon} size={20} />
          <Typography.Text variant="tag" className={styles.Label}>
            {tab.label}
          </Typography.Text>
        </NavLink>
      ))}
    </nav>
  );
};
