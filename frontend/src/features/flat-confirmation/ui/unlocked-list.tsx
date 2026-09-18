import { CellSimple, Flex, Typography } from "@maxhub/max-ui";

import { homeIcon, Icon, meterIcon, pollIcon } from "@/shared/ui/icon";

import styles from "./unlocked-list.module.css";

const UNLOCKED = [
  {
    icon: meterIcon,
    title: "Счётчики",
    subtitle: "Передавайте показания с фото",
  },
  {
    icon: homeIcon,
    title: "Начисления",
    subtitle: "Суммы за месяц и что изменилось",
  },
  {
    icon: pollIcon,
    title: "Опросы",
    subtitle: "Ваш голос учитывается по площади квартиры",
  },
];

export const UnlockedList = () => {
  return (
    <Flex direction="column" align="stretch" gapY={8}>
      <Typography.Text variant="description" color="secondary">
        Теперь вам доступны:
      </Typography.Text>

      <div className={styles.Panel}>
        {UNLOCKED.map((item) => (
          <CellSimple
            key={item.title}
            before={<Icon src={item.icon} className={styles.Icon} />}
            title={item.title}
            subtitle={item.subtitle}
          />
        ))}
      </div>
    </Flex>
  );
};
