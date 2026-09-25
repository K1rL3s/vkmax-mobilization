import { CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";

import styles from "./ways-panel.module.css";

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
        {[
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
        ].map((way) => (
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
