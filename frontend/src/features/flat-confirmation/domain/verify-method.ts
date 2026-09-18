export type VerifyMethod = "account" | "org";

// оба способа принимают одно и то же: лицевой счет и пояснение к нему.
// Комментарий читает только запрос в УК, но подпись общая - иначе выбранный
// способ можно потерять по дороге к отправке
export type VerifyInput = {
  accountNo: string;
  comment: string;
};
