import { Flex, Typography } from "@maxhub/max-ui";

import type { EmergencyContact } from "@/features/emergency";
import { ZONE_LABEL, type RequestCategoryItem } from "@/features/request";
import { alertIcon, buildingIcon, clockIcon, Icon } from "@/shared/ui/icon";

import styles from "./category-info.module.css";

type CategoryInfoProps = {
  category: RequestCategoryItem;
  orgName: string | null;
  emergency: EmergencyContact | null;
};

export const CategoryInfo = ({
  category,
  orgName,
  emergency,
}: CategoryInfoProps) => {
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
              Локализовать аварию - {category.react_text}
            </Typography.Text>
          )}
          <Typography.Text variant="body-strong" color="primary">
            Срок - {category.deadline_text}
          </Typography.Text>
          {category.deadline_basis && (
            <Typography.Text variant="description" color="secondary">
              {category.deadline_basis}
            </Typography.Text>
          )}
        </Flex>
      </Flex>

      {emergency &&
        (category.category === "leak" ||
          category.category === "electricity") && (
          <Flex asChild align="center" gap={12}>
            <a href={`tel:${emergency.phone}`} className={styles.Emergency}>
              <Icon src={alertIcon} className={styles.EmergencyIcon} />
              <Flex align="stretch" direction="column" gapY={2}>
                <Typography.Text variant="description" color="secondary">
                  Течёт или искрит прямо сейчас? Звоните
                </Typography.Text>
                <Typography.Text variant="body-strong" color="primary">
                  {emergency.label}:{" "}
                  <span className={styles.Phone}>{emergency.phone}</span>
                </Typography.Text>
              </Flex>
            </a>
          </Flex>
        )}
    </div>
  );
};
