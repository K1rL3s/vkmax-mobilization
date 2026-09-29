import { CellSimple, Flex, Typography } from "@maxhub/max-ui";

import { useRequestCategories } from "@/features/request";
import type { components } from "@/shared/api/schema/generated";
import { documentIcon, Icon } from "@/shared/ui/icon";
import { StatusPill, type StatusPillTone } from "@/shared/ui/status-pill";

import { worksPeriod, worksState } from "./when";

import styles from "./works.module.css";

type Announcement = components["schemas"]["AnnouncementItem"];

const STATE: Record<
  ReturnType<typeof worksState>,
  { label: string; tone: StatusPillTone }
> = {
  planned: { label: "Запланированы", tone: "themed" },
  going: { label: "Идут", tone: "negative" },
  done: { label: "Завершены", tone: "positive" },
};

export const WorksDetails = ({
  announcement: { works, documents = [] },
}: {
  announcement: Announcement;
}) => {
  const categories = useRequestCategories();
  const category = categories.data?.find(
    (item) => item.category === works?.category,
  )?.label;

  if (!works && documents.length === 0) {
    return null;
  }

  return (
    <Flex align="stretch" direction="column" gapY={8}>
      {works && (
        <Flex align="center" gap={8} wrap="wrap">
          <StatusPill tone={STATE[worksState(works)].tone}>
            {STATE[worksState(works)].label}
          </StatusPill>

          <Typography.Text variant="description" color="secondary">
            {[category, worksPeriod(works)].filter(Boolean).join(" · ")}
          </Typography.Text>
        </Flex>
      )}

      {documents.length > 0 && (
        <div className={styles.Documents}>
          {documents.map((document, index) => (
            <CellSimple
              key={document.name}
              separator={index > 0}
              before={<Icon src={documentIcon} className={styles.Icon} />}
              title={document.title}
              showChevron
              asChild
            >
              <a href={document.url} target="_blank" rel="noreferrer" />
            </CellSimple>
          ))}
        </div>
      )}
    </Flex>
  );
};
