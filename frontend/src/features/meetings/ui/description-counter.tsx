import { useWatch, type Control, type FieldPath } from "react-hook-form";
import { Typography } from "@maxhub/max-ui";

import { pollFormConstraints } from "../domain/poll-draft";

export const DescriptionCounter = <Draft extends { description: string }>({
  control,
  className,
}: {
  control: Control<Draft>;
  className?: string;
}) => {
  const description = useWatch({
    control,
    name: "description" as FieldPath<Draft>,
  });

  return (
    <Typography.Text className={className} variant="detail" color="secondary">
      {String(description).length} / {pollFormConstraints.description}
    </Typography.Text>
  );
};
