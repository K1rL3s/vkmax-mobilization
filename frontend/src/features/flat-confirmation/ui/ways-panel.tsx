import { CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";

import type { VerifyMethod } from "../domain/verify-method";

import styles from "./ways-panel.module.css";

const WAYS: { method: VerifyMethod; title: string; subtitle: string }[] = [
  {
    method: "account",
    title: "По лицевому счёту",
    subtitle: "Номер есть в квитанции",
  },
  {
    method: "org",
    title: "Через УК",
    subtitle: "Отправим запрос в управляющую компанию",
  },
];

type WaysPanelProps = {
  residentId: number;
  returnTo: string;
};

export const WaysPanel = ({ residentId, returnTo }: WaysPanelProps) => {
  return (
    <Flex direction="column" align="stretch" gapY={12}>
      <Typography.Text asChild variant="title" color="primary">
        <h2 className={styles.Title}>Способы подтверждения</h2>
      </Typography.Text>

      <div className={styles.Panel}>
        {WAYS.map((way) => (
          <CellSimple
            key={way.method}
            asChild
            title={way.title}
            subtitle={way.subtitle}
            showChevron
          >
            <Link
              to={generatePath(Routes.FLAT_CONFIRMATION_METHOD, {
                residentId: String(residentId),
                method: way.method,
              })}
              state={{ returnTo }}
            />
          </CellSimple>
        ))}
      </div>
    </Flex>
  );
};
