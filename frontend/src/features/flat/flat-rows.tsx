import type { ReactNode } from "react";
import { CellSimple, Typography } from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";

import type { components } from "@/shared/api/schema/generated";
import { formatArea, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";

type Row = {
  title: string;
  subtitle?: string;
  after?: ReactNode;
  disabled?: boolean;
  showChevron?: boolean;
  onClick?: () => void;
};

const value = (text: string) => (
  <Typography.Text variant="body" color="secondary">
    {text}
  </Typography.Text>
);

export const FlatRows = ({
  flat,
}: {
  flat: components["schemas"]["FlatCard"];
}) => {
  const navigate = useNavigate();
  const isMetersOpen = flat.verified && flat.meters_count > 0;
  const rows: Row[] = [];

  if (flat.entrance != null) {
    rows.push({ title: "Подъезд", after: value(String(flat.entrance)) });
  }

  if (flat.area != null) {
    rows.push({ title: "Площадь", after: value(formatArea(flat.area)) });
  }

  if (flat.account_no != null) {
    rows.push({
      title: "Лицевой счёт",
      after: value(`··· ${flat.account_no}`),
    });
  }

  rows.push({
    title: "Счётчики",
    subtitle: flat.verified
      ? `${flat.meters_count} ${plural(flat.meters_count, ["счётчик", "счётчика", "счётчиков"])}`
      : "после подтверждения",
    disabled: !flat.verified,
    showChevron: isMetersOpen,
    onClick: isMetersOpen ? () => void navigate(Routes.METERS) : undefined,
  });

  rows.push({
    title: "Жители",
    after: value(
      `${flat.residents_count} ${plural(flat.residents_count, ["житель", "жителя", "жителей"])}`,
    ),
  });

  return rows.map((row, index) => (
    <CellSimple key={row.title} separator={index > 0} {...row} />
  ));
};
