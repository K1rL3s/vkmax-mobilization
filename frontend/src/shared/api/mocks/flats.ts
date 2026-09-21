import { badRequest, conflict, forbidden, notFound, ok, route } from "./reply";
import {
  addVerification,
  findFlat,
  flatCard,
  residencies,
  latestVerification,
  residencyForHouse,
  setVerified,
  verificationRequestItem,
} from "./state";

const ALREADY_VERIFIED_DETAIL = "Квартира уже подтверждена";
const FLAT_NOT_FOUND = "Квартира не найдена";

// житель набирает счет с квитанции руками, поэтому пробелы и регистр к делу
// не относятся
const normalizeAccount = (value: string): string =>
  value.replace(/\s+/g, "").toLowerCase();

const text = (value: unknown): string =>
  typeof value === "string" ? value : "";

// доступ дает дом квартиры, а не сама квартира: до подтверждения flat_id у
// привязки может быть пустым
const resolve = (rawFlatId: string) => {
  const flat = findFlat(Number(rawFlatId));

  if (!flat) {
    return null;
  }

  const residency = residencyForHouse(flat.house_id);

  return residency ? { flat, residency } : null;
};

export const flatsConfigs = [
  {
    path: "/flats/:flat_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flat = findFlat(Number(request.params.flat_id));
        // карточку открывает житель именно этой квартиры, а не дома: до
        // подтверждения flat_id у привязки пустой, и открывать нечего
        const residency = residencies().find(
          (item) => item.flat_id === flat?.id,
        );

        return flat && residency
          ? ok(flatCard(flat, residency))
          : notFound(FLAT_NOT_FOUND);
      }),
    ],
  },
  {
    path: "/flats/:flat_id/verify" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const found = resolve(request.params.flat_id);

        if (!found) {
          return notFound(FLAT_NOT_FOUND);
        }

        const { flat, residency } = found;

        if (residency.role === "tenant") {
          return forbidden("Квартиру подтверждает собственник, а не арендатор");
        }

        if (residency.verified) {
          return ok({
            verified: true,
            detail: ALREADY_VERIFIED_DETAIL,
            verification_status: null,
          });
        }

        const matched =
          normalizeAccount(flat.account_no) ===
          normalizeAccount(text(request.body.account_no));

        if (!matched) {
          return ok({
            verified: false,
            detail:
              "Лицевой счет не совпал. Отправьте запрос на подтверждение в управляющую компанию",
            verification_status: latestVerification(flat.id)?.status ?? null,
          });
        }

        setVerified(residency, flat.id);

        return ok({
          verified: true,
          detail: "Квартира подтверждена",
          verification_status: null,
        });
      }),
    ],
  },
  {
    path: "/flats/:flat_id/verification-request" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const found = resolve(request.params.flat_id);

        if (!found) {
          return notFound(FLAT_NOT_FOUND);
        }

        const { flat, residency } = found;
        const accountNo = text(request.body.account_no).trim();

        if (!accountNo) {
          return badRequest("Укажите лицевой счет");
        }

        if (residency.verified) {
          return conflict(ALREADY_VERIFIED_DETAIL);
        }

        if (latestVerification(flat.id)?.status === "pending") {
          return conflict("Заявка на подтверждение уже отправлена");
        }

        const comment = text(request.body.comment).trim();
        const rejected = normalizeAccount(accountNo) === "отказ";
        const created = addVerification(
          flat.id,
          accountNo,
          comment === "" ? null : comment,
          rejected ? "rejected" : "pending",
          rejected ? "Лицевой счет принадлежит другой квартире" : null,
        );

        return ok(verificationRequestItem(created, flat));
      }),
    ],
  },
];
