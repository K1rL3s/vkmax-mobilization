import type { components } from "@/shared/api/schema/generated";

export type Resident = components["schemas"]["HouseResidentItem"];

export type ResidentActionKind =
  "chairman" | "unchairman" | "revoke" | "block" | "unblock";

type ResidentAction = {
  kind: ResidentActionKind;
  label: string;
  destructive: boolean;
  refusal: string | null;
};

const ROLE_LABEL: Record<Resident["role"], string> = {
  owner: "собственник",
  tenant: "арендатор",
};

export const reasonFormConstraints = {
  reasonMin: 10,
  reasonMax: 300,
};

export const residentPlace = (resident: Resident) =>
  `${resident.flat_number ? `Кв. ${resident.flat_number}` : "Квартира не указана"} · ${ROLE_LABEL[resident.role]}`;

export const residentActions = (resident: Resident): ResidentAction[] => [
  resident.is_chairman
    ? {
        kind: "unchairman",
        label: "Снять с должности председателя",
        destructive: true,
        refusal: null,
      }
    : {
        kind: "chairman",
        label: "Назначить председателем",
        destructive: false,
        refusal: !resident.verified
          ? "Председателем становится житель с подтверждённой квартирой"
          : resident.status === "blocked"
            ? "Житель заблокирован: сначала разблокируйте его"
            : null,
      },
  {
    kind: "revoke",
    label: "Отозвать подтверждение квартиры",
    destructive: true,
    refusal: resident.verified
      ? null
      : "Квартира не подтверждена, отзывать нечего",
  },
  resident.status === "blocked"
    ? {
        kind: "unblock",
        label: "Разблокировать",
        destructive: false,
        refusal: null,
      }
    : {
        kind: "block",
        label: "Заблокировать в доме",
        destructive: true,
        refusal: resident.is_chairman
          ? "Председателя совета дома заблокировать нельзя: сначала снимите его с должности"
          : null,
      },
];
