import { Typography } from "@maxhub/max-ui";
import { NavLink } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import {
  Icon,
  navHomeIcon,
  navProfileIcon,
  navRequestsIcon,
  pollIcon,
} from "@/shared/ui/icon";

import styles from "./tab-bar.module.css";

export const TabBar = () => {
  return (
    <nav className={styles.TabBar}>
      {[
        { to: Routes.HOME, label: "Главная", icon: navHomeIcon },
        { to: Routes.REQUESTS, label: "Заявки", icon: navRequestsIcon },
        { to: Routes.MEETINGS, label: "Опросы", icon: pollIcon },
        { to: Routes.PROFILE, label: "Профиль", icon: navProfileIcon },
      ].map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === Routes.HOME}
          className={({ isActive }) =>
            cn(styles.Tab, isActive && styles.TabActive)
          }
        >
          <Icon src={tab.icon} size={20} />
          <Typography.Text variant="tag">{tab.label}</Typography.Text>
        </NavLink>
      ))}
    </nav>
  );
};
