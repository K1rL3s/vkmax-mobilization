import { relativeDay } from "@/shared/lib/format";

import type { RequestMessage } from "./types";

type MessageDay = {
  day: string;
  label: string | null;
  messages: RequestMessage[];
};

export const groupMessagesByDay = (messages: RequestMessage[]) => {
  const days: MessageDay[] = [];

  for (const message of messages) {
    const day = new Date(message.created_at).toDateString();
    const last = days.at(-1);

    if (last?.day === day) {
      last.messages.push(message);
    } else {
      days.push({
        day,
        label: relativeDay(message.created_at),
        messages: [message],
      });
    }
  }

  return days;
};
