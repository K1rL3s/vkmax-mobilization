import { Typography } from "@maxhub/max-ui";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { orgParams, useSession } from "@/shared/model/session";
import {
  alertIcon,
  buildingIcon,
  chartIcon,
  homeIcon,
  Icon,
  megaphoneIcon,
  navMeetingsIcon,
  navRequestsIcon,
  pollIcon,
} from "@/shared/ui/icon";
import { StripButton } from "@/shared/ui/strip-button";

import styles from "./admin-tab-bar.module.css";

export const AdminTabBar = () => {
  const navigate = useNavigate();
  const { currentResidency, selectCabinet } = useSession();
  const danger = rqClient.useQuery("get", "/api/admin/requests", {
    params: {
      ...orgParams(),
      query: { danger: true, grouped: true, limit: 1 },
    },
  });
  const dangerCount = danger.data?.total ?? 0;

  const exit = currentResidency
    ? { label: "Кабинет жителя", to: Routes.HOME }
    : { label: "Привязать квартиру", to: Routes.ONBOARDING_HOUSE };

  const leave = () => {
    selectCabinet("resident");
    void navigate(exit.to, { replace: true });
  };

  return (
    <nav className={styles.AdminTabBar}>
      {dangerCount > 0 && (
        <Link
          to={`${Routes.ADMIN_REQUESTS}?filter=danger`}
          className={styles.DangerBanner}
        >
          <Icon src={alertIcon} size={20} />
          <Typography.Text variant="body-strong" color="inherit">
            Аварии: {dangerCount} - нужно немедленное вмешательство
          </Typography.Text>
        </Link>
      )}

      <StripButton icon={homeIcon} label={exit.label} onClick={leave} />

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
