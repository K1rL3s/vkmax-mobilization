import { useWatch, type Control } from "react-hook-form";
import { Typography } from "@maxhub/max-ui";

import { pollFormConstraints, type PollDraft } from "../domain/poll-draft";

export const DescriptionCounter = ({
  control,
  className,
}: {
  control: Control<PollDraft>;
  className?: string;
}) => {
  const description = useWatch({ control, name: "description" });

  return (
    <Typography.Text className={className} variant="detail" color="secondary">
      {description.length} / {pollFormConstraints.description}
    </Typography.Text>
  );
};
