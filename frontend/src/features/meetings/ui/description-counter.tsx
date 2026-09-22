import { useWatch, type Control } from "react-hook-form";
import { Typography } from "@maxhub/max-ui";

import { pollFormConstraints } from "../domain/poll-form-constraints";
import type { PollDraft } from "../domain/poll-draft";

// счётчик подписан на поле сам: подписка в хуке формы перерисовывала бы весь
// экран на каждое нажатие клавиши, хотя меняется одна строка
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
