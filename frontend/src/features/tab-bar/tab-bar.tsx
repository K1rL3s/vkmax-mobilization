import { useState } from "react";
import { Button, CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { NavLink, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { useSession, workingOrgs } from "@/shared/model/session";
import { BottomSheet } from "@/shared/ui/bottom-sheet";
import {
  buildingIcon,
  Icon,
  navHomeIcon,
  navProfileIcon,
  navRequestsIcon,
  pollIcon,
} from "@/shared/ui/icon";
import { StatusPill } from "@/shared/ui/status-pill";
import { StripButton } from "@/shared/ui/strip-button";

import styles from "./tab-bar.module.css";

export const TabBar = () => {
  const navigate = useNavigate();
  const { session, openedOrg, selectCabinet, selectOrg } = useSession();
  const orgs = workingOrgs(session);
  const [picking, setPicking] = useState(false);

  const enter = async (orgId: number) => {
    setPicking(false);
    if (orgId !== openedOrg?.org_id) {
      await selectOrg(orgId);
    }
    selectCabinet("admin");
    await navigate(Routes.ADMIN, { replace: true });
  };

  const openCabinet = () => {
    const target = openedOrg ?? (orgs.length === 1 ? orgs[0] : undefined);

    if (target) {
      void enter(target.org_id);
    } else {
      setPicking(true);
    }
  };

  return (
    <nav className={styles.TabBar}>
      {orgs.length > 0 && (
        <StripButton
          icon={buildingIcon}
          label="Кабинет УК"
          onClick={openCabinet}
        />
      )}

      <div className={styles.Tabs}>
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
      </div>

      <BottomSheet isOpen={picking} onClose={() => setPicking(false)}>
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.SheetTitle}>Кабинет УК</h2>
          </Typography.Text>
          <div className={styles.Orgs}>
            {orgs.map((org, index) => (
              <CellSimple
                key={org.org_id}
                separator={index > 0}
                before={<Icon src={buildingIcon} />}
                title={org.name}
                after={
                  org.is_demo && <StatusPill tone="themed">демо</StatusPill>
                }
                showChevron
                onClick={() => void enter(org.org_id)}
              />
            ))}
          </div>
          <Button
            size="large"
            variant="secondary"
            stretched
            onClick={() => setPicking(false)}
          >
            Отмена
          </Button>
        </Flex>
      </BottomSheet>
    </nav>
  );
};
