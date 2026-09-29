import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  notFound,
  ok,
  type MockHttpRequest,
} from "./reply";
import {
  addVerification,
  findFlat,
  flatCard,
  latestVerification,
  residencyForFlat,
  residencyForHouse,
  setVerified,
  verificationRequestItem,
} from "./state";

const normalizeAccount = (value: string): string =>
  value.replace(/\s+/g, "").toLowerCase();

const text = (value: unknown): string =>
  typeof value === "string" ? value : "";

const resolve = (request: MockHttpRequest) => {
  const flat = findFlat(Number(request.params.flat_id));
  const residency = flat && residencyForHouse(flat.house_id);

  return flat && residency ? { flat, residency } : null;
};

export const flatsConfigs = [
  endpoint("get", "/flats/:flat_id", (request) => {
    const flat = findFlat(Number(request.params.flat_id));
    const residency = flat && residencyForFlat(flat.id);

    return flat && residency
      ? ok(flatCard(flat, residency))
      : notFound("Квартира не найдена");
  }),
  endpoint("post", "/flats/:flat_id/verify", (request) => {
    const found = resolve(request);

    if (!found) {
      return notFound("Квартира не найдена");
    }

    const { flat, residency } = found;

    if (residency.role === "tenant") {
      return forbidden("Квартиру подтверждает собственник, а не арендатор");
    }

    if (residency.verified) {
      return ok({
        verified: true,
        detail: "Квартира уже подтверждена",
        verification_status: null,
      });
    }

    const stated =
      /\|persacc=([^|]*)/i.exec(text(request.body.payment_qr))?.[1] ??
      text(request.body.account_no);

    if (normalizeAccount(flat.account_no) !== normalizeAccount(stated)) {
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
  endpoint("post", "/flats/:flat_id/verification-request", (request) => {
    const found = resolve(request);

    if (!found) {
      return notFound("Квартира не найдена");
    }

    const { flat, residency } = found;
    const accountNo = text(request.body.account_no).trim();

    if (!accountNo) {
      return badRequest("Укажите лицевой счет");
    }

    if (residency.verified) {
      return conflict("Квартира уже подтверждена");
    }

    if (latestVerification(flat.id)?.status === "pending") {
      return conflict("Заявка на подтверждение уже отправлена");
    }

    const comment = text(request.body.comment).trim();
    const rejected = normalizeAccount(accountNo) === "отказ";

    return ok(
      verificationRequestItem(
        addVerification(
          flat.id,
          accountNo,
          comment || null,
          rejected ? "rejected" : "pending",
          rejected ? "Лицевой счет принадлежит другой квартире" : null,
        ),
        flat,
      ),
    );
  }),
];
