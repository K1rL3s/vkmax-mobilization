import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useRef, useState } from "react";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { Chevron } from "@/shared/ui/chevron";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import styles from "./house-card.module.css";

type Item = components["schemas"]["Pp290Item"];

const byPoint = (items: Item[]) => {
  const points = new Map<string, Item[]>();

  for (const item of items) {
    const point = item.ref.split(",")[0];
    points.set(point, [...(points.get(point) ?? []), item]);
  }

  return [...points];
};

const Point = ({ point, items }: { point: string; items: Item[] }) => {
  const { section } = items[0];
  const works = items.filter((item) => item.text !== section);
  const title = (
    <Flex direction="column" gapY={2} className={styles.Grow}>
      <Typography.Text variant="description" color="secondary">
        {point}
      </Typography.Text>
      <Typography.Text variant="body" color="primary">
        {section}
      </Typography.Text>
    </Flex>
  );

  if (works.length === 0) {
    return <div className={styles.Point}>{title}</div>;
  }

  return (
    <details className={styles.Point}>
      <summary className={styles.PointTitle}>
        {title}
        <span className={styles.Chevron}>
          <Chevron />
        </span>
      </summary>
      <ul className={styles.Works}>
        {works.map((work) => (
          <li key={work.ref}>
            <Typography.Text variant="body" color="primary">
              {work.text}
            </Typography.Text>
          </li>
        ))}
      </ul>
    </details>
  );
};

export const Pp290Section = () => {
  const [open, setOpen] = useState(false);
  const section = useRef<HTMLElement>(null);
  const query = rqClient.useQuery(
    "get",
    "/api/pp290",
    { params: authParams() },
    { enabled: open, staleTime: Infinity },
  );

  const collapse = () => {
    if (section.current && section.current.getBoundingClientRect().top < 0) {
      section.current.scrollIntoView();
    }

    setOpen(false);
  };

  const content = () => {
    if (!open) {
      return (
        <Button
          size="large"
          variant="secondary"
          stretched
          onClick={() => setOpen(true)}
        >
          Показать перечень работ
        </Button>
      );
    }

    if (query.isPending) {
      return <LoadingState title="Загружаем перечень" />;
    }

    if (query.isError) {
      return (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      );
    }

    return (
      <>
        <div className={styles.Panel}>
          {byPoint(query.data.items).map(([point, items]) => (
            <Point key={point} point={point} items={items} />
          ))}
        </div>
        <Typography.Text variant="description" color="secondary">
          ПП РФ № 290 {query.data.edition}
        </Typography.Text>
        <Button size="large" variant="secondary" stretched onClick={collapse}>
          Свернуть перечень
        </Button>
      </>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section ref={section}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Что УК обязана делать</h2>
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Минимальный перечень работ по содержанию общего имущества, который УК
          выполняет в каждом доме. На его пункты ссылаются заявка и жалоба в ГЖИ
        </Typography.Text>
        {content()}
      </section>
    </Flex>
  );
};
