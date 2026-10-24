import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import type { PeriodDays } from "../domain/period";
import { useArrivals } from "../model/use-arrivals";

import { Section } from "./section";
import { SplitRows } from "./split-rows";

const ARRIVAL_LABEL: Record<components["schemas"]["ArrivalSource"], string> = {
  self: "Нашли дом сами",
  qr: "QR в подъезде",
  chat: "Чат дома",
  invite: "Позвали соседи",
  other: "Другое",
};

export const ArrivalsSection = ({ period }: { period: PeriodDays }) => {
  const arrivals = useArrivals(period);

  return (
    <Section
      title="Откуда пришли жители"
      isPending={arrivals.isPending}
      isError={arrivals.isError}
      error={arrivals.error}
      onRetry={() => void arrivals.refetch()}
    >
      {arrivals.data?.is_empty ? (
        <EmptyState
          title="За период новых жителей нет"
          description="Выберите период длиннее"
        />
      ) : (
        <SplitRows
          rows={(arrivals.data?.items ?? []).map((item) => ({
            key: item.source,
            label: ARRIVAL_LABEL[item.source],
            count: item.count,
            share: item.share,
          }))}
        />
      )}
    </Section>
  );
};
