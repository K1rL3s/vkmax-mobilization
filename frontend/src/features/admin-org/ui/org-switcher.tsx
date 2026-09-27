import { CellSimple, Flex, Radio, Typography } from "@maxhub/max-ui";

import { useSession, workingOrgs } from "@/shared/model/session";
import { StatusPill } from "@/shared/ui/status-pill";

import { ROLE_LABEL } from "../domain/roles";

import styles from "./org-switcher.module.css";

export const OrgSwitcher = () => {
  const { session, currentOrg, selectOrg } = useSession();
  const orgs = workingOrgs(session);

  if (orgs.length < 2) return null;

  return (
    <Flex asChild align="stretch" direction="column" gapY={8}>
      <section className={styles.OrgSwitcher}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Где вы работаете</h2>
        </Typography.Text>

        <div className={styles.Panel}>
          {orgs.map((org, index) => (
            <CellSimple
              key={org.org_id}
              as="label"
              separator={index > 0}
              innerClassNames={{ title: styles.Title, content: styles.Content }}
              title={
                <Flex align="center" gap={8}>
                  <span className={styles.Name}>{org.name}</span>
                  {org.is_demo && <StatusPill tone="themed">демо</StatusPill>}
                </Flex>
              }
              subtitle={ROLE_LABEL[org.role]}
              after={
                <Radio
                  name="org"
                  checked={org.org_id === currentOrg?.org_id}
                  onChange={() => void selectOrg(org.org_id)}
                />
              }
            />
          ))}
        </div>

        <Typography.Text variant="description" color="secondary">
          Все вкладки кабинета покажут выбранную организацию
        </Typography.Text>
      </section>
    </Flex>
  );
};
