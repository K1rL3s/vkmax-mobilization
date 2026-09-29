import { type ComponentProps, useState } from "react";
import { Input } from "@maxhub/max-ui";

import { isoFromMasked, maskDate, maskedFromIso } from "@/shared/lib/date-mask";

type DateInputProps = Omit<
  ComponentProps<typeof Input>,
  "value" | "onChange" | "type"
> & {
  value: string;
  onChange: (iso: string) => void;
};

export const DateInput = ({ value, onChange, ...props }: DateInputProps) => {
  const [text, setText] = useState(() => maskedFromIso(value));
  const shown = isoFromMasked(text) === value ? text : maskedFromIso(value);

  return (
    <Input
      {...props}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder="ДД.ММ.ГГГГ"
      maxLength={10}
      value={shown}
      onChange={(event) => {
        const next = maskDate(event.target.value);
        setText(next);
        onChange(isoFromMasked(next));
      }}
    />
  );
};
