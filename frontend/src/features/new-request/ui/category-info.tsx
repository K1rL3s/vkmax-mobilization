import { Flex, Typography } from "@maxhub/max-ui";

import {
  NO_NORM,
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
          {category.react_text && (
            <Typography.Text variant="body-strong" color="primary">
              Принять - {category.react_text}
            </Typography.Text>
          )}
          <Typography.Text variant="body-strong" color="primary">
            Срок - {category.deadline_text}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {category.deadline_basis ?? NO_NORM}
          </Typography.Text>
        </Flex>
      </Flex>
    </div>
  );
};
