import {
  Button,
  CellList,
  CellSimple,
  Panel,
  Typography,
} from "@maxhub/max-ui";
import { Link, useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { useSession, type Residency } from "@/shared/model/session";
import { checkIcon, homeIcon, Icon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./residencies.module.css";

const flatOf = (residency: Residency) => {
  if (residency.flat_number === null || residency.flat_number === undefined) {
    return "Квартира не выбрана";
  }

  return `кв. ${residency.flat_number} · ${residency.verified ? "подтверждена" : "нужно подтвердить"}`;
};

const ResidenciesPage = () => {
  const navigate = useNavigate();
  const { residencies, currentResidency, select } = useSession();

  const open = async (residency: Residency) => {
    if (residency.resident_id !== currentResidency?.resident_id) {
      await select(residency.resident_id);
    }

    await navigate(Routes.HOME);
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <CellList mode="island">
        {residencies.map((residency) => {
          const isCurrent =
            residency.resident_id === currentResidency?.resident_id;

          return (
            <CellSimple
              key={residency.resident_id}
              before={
                <IconTile
                  icon={homeIcon}
                  tone={isCurrent ? "themed" : "neutral"}
                />
              }
              title={residency.address}
              subtitle={flatOf(residency)}
              after={
                isCurrent && <Icon src={checkIcon} className={styles.Check} />
              }
              onClick={() => void open(residency)}
            />
          );
        })}
      </CellList>

      <Button asChild size="large" variant="secondary" stretched>
        <Link to={Routes.ONBOARDING_HOUSE}>Добавить дом</Link>
      </Button>

      <Typography.Text
        variant="description"
        color="tertiary"
        className={styles.Note}
      >
        Заявки, показания и собрания кабинет показывает для выбранного адреса
      </Typography.Text>
    </Panel>
  );
};

export const Component = ResidenciesPage;
