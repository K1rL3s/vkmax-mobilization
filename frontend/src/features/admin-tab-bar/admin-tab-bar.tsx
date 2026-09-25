import { Tappable, Typography } from "@maxhub/max-ui";
import { NavLink, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import {
  buildingIcon,
  chartIcon,
  chevronSmallIcon,
  Icon,
  megaphoneIcon,
  navMeetingsIcon,
  navRequestsIcon,
  pollIcon,
} from "@/shared/ui/icon";

import styles from "./admin-tab-bar.module.css";

export const AdminTabBar = () => {
  const navigate = useNavigate();
  const { currentResidency, selectCabinet } = useSession();

  const exit = currentResidency
    ? { label: "Кабинет жителя", to: Routes.HOME }
    : { label: "Привязать квартиру", to: Routes.ONBOARDING_HOUSE };

  const leave = () => {
    selectCabinet("resident");
    void navigate(exit.to, { replace: true });
  };

  return (
    <nav className={styles.AdminTabBar}>
      <Tappable className={styles.Exit} onClick={leave}>
        <Icon src={chevronSmallIcon} size={10} className={styles.ExitArrow} />
        <Typography.Text variant="tag" color="primary">
          {exit.label}
        </Typography.Text>
      </Tappable>

      <div className={styles.Tabs}>
        {[
          { to: Routes.ADMIN_REQUESTS, label: "Заявки", icon: navRequestsIcon },
          {
            to: Routes.ADMIN_ANNOUNCEMENTS,
            label: "Объявления",
            icon: megaphoneIcon,
          },
          { to: Routes.ADMIN_POLLS, label: "Опросы", icon: pollIcon },
          { to: Routes.ADMIN_RECEPTION, label: "Приём", icon: navMeetingsIcon },
          { to: Routes.ADMIN_HOUSES, label: "Дома", icon: buildingIcon },
          { to: Routes.ADMIN_ANALYTICS, label: "Аналитика", icon: chartIcon },
        ].map((tab) => (
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
      </div>
    </nav>
  );
};
