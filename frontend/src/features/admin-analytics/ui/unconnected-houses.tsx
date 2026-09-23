import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";

import styles from "./unconnected-houses.module.css";

type UnconnectedHouse = components["schemas"]["UnconnectedHouseItem"];

const VISIBLE = 10;

export const UnconnectedHouses = ({
  houses,
}: {
  houses: UnconnectedHouse[];
}) => {
  const [expanded, setExpanded] = useState(false);
  const rest = houses.length - VISIBLE;

  return (
    <Flex direction="column" align="stretch" gapY={10}>
      {(expanded ? houses : houses.slice(0, VISIBLE)).map((house) => (
        /* строки неинтерактивны: действия по чужому дому у УК нет */
        <Flex
          key={house.house_id}
          align="baseline"
          justify="space-between"
          gap={12}
        >
          <Typography.Text variant="detail" color="primary">
            {house.address}
          </Typography.Text>

          <Typography.Text
            className={styles.Waiting}
            variant="detail"
            color="secondary"
          >
            {house.waiting} ждут
          </Typography.Text>
        </Flex>
      ))}

      {!expanded && rest > 0 && (
        <Button
          size="small"
          variant="secondary"
          onClick={() => setExpanded(true)}
        >
          Показать все ещё {rest}
        </Button>
      )}
    </Flex>
  );
};
