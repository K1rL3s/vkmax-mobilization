import { Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { cn } from "@/shared/lib/css";

import { splitTiles, tileView } from "../domain/tile";

import styles from "./tiles-section.module.css";

type DashboardTile = components["schemas"]["DashboardTile"];

const TileGroup = ({
  title,
  tiles,
}: {
  title: string;
  tiles: DashboardTile[];
}) => {
  if (tiles.length === 0) {
    return null;
  }

  return (
    <Flex direction="column" align="stretch" gapY={8}>
      <Typography.Text variant="detail-strong" color="secondary">
        {title}
      </Typography.Text>

      <div className={styles.Grid}>
        {tiles.map(tileView).map((tile) => (
          <Flex
            key={tile.key}
            className={styles.Tile}
            direction="column"
            align="stretch"
            gapY={2}
          >
            <Typography.Text
              className={cn(styles.Value, tile.isAlert && styles.alert)}
              variant="header"
              color="inherit"
            >
              {tile.value}
            </Typography.Text>

            <Typography.Text variant="detail" color="secondary">
              {tile.label}
            </Typography.Text>

            {tile.note && (
              <Typography.Text variant="detail" color="tertiary">
                {tile.note}
              </Typography.Text>
            )}
          </Flex>
        ))}
      </div>
    </Flex>
  );
};

export const TilesSection = ({ tiles }: { tiles: DashboardTile[] }) => {
  const { now, period } = splitTiles(tiles);

  return (
    <Flex direction="column" align="stretch" gapY={16}>
      <TileGroup title="Сейчас" tiles={now} />
      <TileGroup title="За период" tiles={period} />
    </Flex>
  );
};
