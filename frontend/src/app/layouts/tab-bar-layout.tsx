import { Typography } from "@maxhub/max-ui";
import { NavLink, Outlet } from "react-router-dom";

import {
  navHomeIcon,
  navMeetingsIcon,
  navProfileIcon,
  navRequestsIcon,
} from "@/shared/assets/icons";
import { cn } from "@/shared/helpers/cn";
import { Routes } from "@/shared/model/routes";
import { Icon } from "@/shared/ui/icon";

import styles from "./tab-bar-layout.module.css";

const TABS = [
  { to: Routes.HOME, label: "Главная", icon: navHomeIcon },
  { to: Routes.REQUESTS, label: "Заявки", icon: navRequestsIcon },
  { to: Routes.MEETINGS, label: "Собрания", icon: navMeetingsIcon },
  { to: Routes.PROFILE, label: "Профиль", icon: navProfileIcon },
];

export const TabBarLayout = () => {
  return (
    <div className={styles.Layout}>
      <main className={styles.Content}>
        <Outlet />
      </main>

      <nav className={styles.TabBar}>
        {TABS.map((tab) => (
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
    </div>
  );
};
