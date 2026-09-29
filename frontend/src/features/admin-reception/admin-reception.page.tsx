import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { AccessSection } from "./ui/access-section";
import { AppointmentsSection } from "./ui/appointments-section";
import { HoursSection } from "./ui/hours-section";

import styles from "./admin-reception.module.css";

const AdminReceptionPage = () => (
  <Panel className={styles.Page} mode="secondary">
    <Flex align="stretch" direction="column" gapY={4}>
      <Typography.Text asChild variant="header" color="primary">
        <h1>Приём</h1>
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        Часы приёма организации, записи жителей по дням и сборы доступа в
        квартиры
      </Typography.Text>
    </Flex>

    <HoursSection />

    <AppointmentsSection />

    <AccessSection />
  </Panel>
);

export const Component = AdminReceptionPage;
