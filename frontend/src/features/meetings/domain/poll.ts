import type { components } from "@/shared/api/schema/generated";
import { formatDay, plural } from "@/shared/lib/format";
import type { Residency } from "@/shared/model/session";

export type PollListItem = components["schemas"]["PollListItem"];

export type PollCard = components["schemas"]["PollCard"];

export type PollResults = components["schemas"]["PollResults"];

type PollNonVoter = components["schemas"]["PollNonVoterItem"];

export const groupByEntrance = (flats: PollNonVoter[]) => {
  const groups: { title: string; flats: PollNonVoter[] }[] = [];

  for (const flat of flats) {
    const title =
      flat.entrance === null ? "Без подъезда" : `Подъезд ${flat.entrance}`;
    const current = groups.at(-1);

    if (current?.title === title) {
      current.flats.push(flat);
    } else {
      groups.push({ title, flats: [flat] });
    }
  }

  return groups;
};

export const authorCaption = (role: string) => {
  if (role === "chairman") {
    return "Опрос председателя совета дома";
  }

  return role === "staff" ? "Опрос управляющей компании" : "Опрос дома";
};

export const deadlineLabel = (poll: PollListItem) => {
  if (poll.status === "active") {
    return `Голосование до ${formatDay(poll.ends_at)}`;
  }

  return new Date(poll.ends_at) > new Date()
    ? "Завершён досрочно"
    : `Завершён ${formatDay(poll.ends_at)}`;
};

export const flatsCount = (count: number) =>
  `${count} ${plural(count, ["квартира", "квартиры", "квартир"])}`;

export const votedLine = (poll: PollListItem) => {
  if (poll.voted) {
    return `Вы проголосовали · ${flatsCount(poll.voted_flats)}`;
  }

  return poll.voted_flats === 0
    ? "Пока никто не проголосовал"
    : `${flatsCount(poll.voted_flats)} ${plural(poll.voted_flats, ["проголосовала", "проголосовали", "проголосовали"])}`;
};

export const voteNote = (
  poll: PollCard,
  residency: Residency | undefined,
): { text: string; confirm: boolean } | null => {
  const weightless =
    residency !== undefined &&
    !residency.verified &&
    residency.flat_id !== null;

  if (poll.voted) {
    if (weightless) {
      return {
        text: "Ваш голос учтён как мнение: квартира не подтверждена, в кворум он не идёт.",
        confirm: true,
      };
    }

    return {
      text:
        poll.status === "closed"
          ? "Опрос завершён, ваш голос учтён."
          : "Ваш голос учтён. Изменить его нельзя.",
      confirm: false,
    };
  }

  if (poll.status === "closed") {
    return { text: "Опрос завершён, голосование закрыто.", confirm: false };
  }

  if (residency === undefined) {
    return null;
  }

  if (!residency.is_connected) {
    return {
      text: "Дом ещё не подключён к сервису: голосование появится вместе с УК.",
      confirm: false,
    };
  }

  if (residency.role === "tenant") {
    return {
      text: "За квартиру голосует собственник: арендатор в опросах не участвует.",
      confirm: false,
    };
  }

  if (residency.flat_id === null) {
    return {
      text: residency.flat_number
        ? "УК ещё не добавила вашу квартиру: голос учтётся как мнение, без веса в кворуме."
        : "Квартира не выбрана: голос учтётся как мнение, без веса в кворуме.",
      confirm: false,
    };
  }

  return weightless
    ? {
        text: "Квартира не подтверждена: голос учтётся как мнение, без веса в кворуме.",
        confirm: true,
      }
    : null;
};

export const weightlessLine = (count: number) =>
  `${count} ${plural(count, ["голос учтён", "голоса учтены", "голосов учтены"])} как ${plural(count, ["мнение", "мнения", "мнения"])} без веса: квартира не подтверждена или за неё уже проголосовал другой собственник.`;
