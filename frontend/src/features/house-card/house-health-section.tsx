import { CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import type { components } from "@/shared/api/schema/generated";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import {
  bulbIcon,
  buildingIcon,
  dropletIcon,
  elevatorIcon,
  flameIcon,
  Icon,
  trashIcon,
  treeIcon,
  usersIcon,
} from "@/shared/ui/icon";

import styles from "./house-card.module.css";

type SystemHealth = components["schemas"]["HouseSystemHealth"];

const SYSTEM: Record<SystemHealth["system"], { label: string; icon: string }> =
  {
    elevator: { label: "Лифт", icon: elevatorIcon },
    water: { label: "Вода", icon: dropletIcon },
    heating: { label: "Отопление", icon: flameIcon },
    electricity: { label: "Электричество", icon: bulbIcon },
    garbage: { label: "Мусор", icon: trashIcon },
    entrance: { label: "Подъезд", icon: buildingIcon },
    yard: { label: "Двор", icon: treeIcon },
  };

const summary = (row: SystemHealth) =>
  row.reported === 0
    ? "В норме"
    : `Были обращения: ${row.reported}, решено ${row.resolved}`;

export const HouseHealthSection = ({
  health,
  withNeighbours,
}: {
  health: SystemHealth[];
  withNeighbours: boolean;
}) => (
  <Flex asChild align="stretch" direction="column" gap={8}>
    <section>
      <Typography.Text asChild variant="title" color="primary">
        <h2>Состояние дома за 14 дней</h2>
      </Typography.Text>
      <div className={styles.Panel}>
        {health.map((row, index) => (
          <CellSimple
            key={row.system}
            separator={index > 0}
            before={
              <Icon
                src={SYSTEM[row.system].icon}
                className={cn(
                  styles.CellIcon,
                  row.open > 0 && styles.attention,
                )}
              />
            }
            title={SYSTEM[row.system].label}
            subtitle={summary(row)}
          />
        ))}
        {withNeighbours && (
          <CellSimple
            separator
            before={<Icon src={usersIcon} className={styles.CellIcon} />}
            title="Что сообщили соседи"
            showChevron
            asChild
          >
            <Link to={Routes.HOUSE_PROBLEMS} />
          </CellSimple>
        )}
      </div>
      <Typography.Text variant="description" color="secondary">
        Только общие заявки дома, личные заявки квартир не учитываются
      </Typography.Text>
    </section>
  </Flex>
);
