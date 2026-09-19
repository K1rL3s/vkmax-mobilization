import { Flex, Typography } from "@maxhub/max-ui";

import {
  plural,
  ZONE_LABEL,
  type RequestCategoryItem,
} from "@/features/request";
import { buildingIcon, clockIcon, Icon } from "@/shared/ui/icon";

import styles from "./category-info.module.css";

type CategoryInfoProps = {
  category: RequestCategoryItem;
  orgName: string | null;
};

export const CategoryInfo = ({ category, orgName }: CategoryInfoProps) => {
  const hours = category.normative_hours;
  const responsible =
    category.zone === "management"
      ? (orgName ?? "Управляющая компания дома")
      : ZONE_LABEL[category.zone];

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={12}>
        <Icon src={buildingIcon} className={styles.Icon} />
        <Flex align="stretch" direction="column" gapY={2}>
          <Typography.Text variant="description" color="secondary">
            Отвечает
          </Typography.Text>
          <Typography.Text variant="body-strong" color="primary">
            {responsible}
          </Typography.Text>
        </Flex>
      </Flex>

      <Flex align="center" gap={12}>
        <Icon src={clockIcon} className={styles.Icon} />
        <Flex align="stretch" direction="column" gapY={2}>
          <Typography.Text variant="body-strong" color="primary">
            Реакция до {hours} {plural(hours, ["часа", "часов", "часов"])}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Нормативный срок для этой категории
          </Typography.Text>
        </Flex>
      </Flex>
    </div>
  );
};
