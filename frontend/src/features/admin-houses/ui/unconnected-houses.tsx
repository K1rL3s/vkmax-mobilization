import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import { rqClient } from "@/shared/api/instance";
import { plural } from "@/shared/lib/format";
import { orgParams } from "@/shared/model/session";

import styles from "./unconnected-houses.module.css";

const VISIBLE = 10;

export const UnconnectedHouses = () => {
  const benchmark = rqClient.useQuery("get", "/api/admin/analytics/benchmark", {
    params: orgParams(),
  });
  const [expanded, setExpanded] = useState(false);
  const houses = benchmark.data?.unconnected_houses ?? [];
  const rest = houses.length - VISIBLE;

  if (houses.length === 0) {
    return null;
  }

  return (
    <Flex asChild direction="column" align="stretch" gapY={8}>
      <section className={styles.Section}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Ждут подключения</h2>
        </Typography.Text>

        <Flex
          className={styles.Card}
          direction="column"
          align="stretch"
          gapY={12}
        >
          {(expanded ? houses : houses.slice(0, VISIBLE)).map((house) => (
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
                {house.waiting}{" "}
                {plural(house.waiting, ["ждёт", "ждут", "ждут"])}
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
      </section>
    </Flex>
  );
};
