import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { plural } from "@/shared/lib/format";
import { Checkbox } from "@/shared/ui/checkbox";
import { StatusPill } from "@/shared/ui/status-pill";

import { MAP_KINDS, type MapKind } from "../model/use-public-map";

import styles from "./map-filters.module.css";

type MapFiltersProps = {
  kind: MapKind;
  org: readonly number[];
  orgs: components["schemas"]["MapOrg"][];
  onKindChange: (kind: MapKind) => void;
  onOrgToggle: (id: number) => void;
};

export const MapFilters = ({
  kind,
  org,
  orgs,
  onKindChange,
  onOrgToggle,
}: MapFiltersProps) => (
  <Flex direction="column" align="stretch" gapY={12}>
    <Typography.Text asChild variant="title" color="primary">
      <h2 className={styles.Title}>Какие дома показать</h2>
    </Typography.Text>

    <Flex wrap="wrap" gapX={8} gapY={4} className={styles.Kinds}>
      {MAP_KINDS.map((choice) => (
        <Button
          key={choice.id}
          type="button"
          size="small"
          variant={choice.id === kind ? "primary" : "secondary"}
          aria-pressed={choice.id === kind}
          onClick={() => onKindChange(choice.id)}
        >
          {choice.label}
        </Button>
      ))}
    </Flex>

    {orgs.length > 0 && (
      <Flex direction="column" align="stretch" gapY={12}>
        <Typography.Text variant="description" color="secondary">
          УК в этой части карты
        </Typography.Text>
        {orgs.map((item) => (
          <Checkbox
            key={item.id}
            className={styles.Org}
            checked={org.includes(item.id)}
            onChange={() => onOrgToggle(item.id)}
          >
            <Flex direction="column" gapY={2}>
              <Flex align="center" gap={8} wrap="wrap">
                <Typography.Text variant="body" color="primary">
                  {item.name}
                </Typography.Text>
                {item.is_demo && <StatusPill tone="neutral">демо</StatusPill>}
              </Flex>
              <Typography.Text variant="description" color="secondary">
                {item.houses} {plural(item.houses, ["дом", "дома", "домов"])}
              </Typography.Text>
            </Flex>
          </Checkbox>
        ))}
      </Flex>
    )}
  </Flex>
);
