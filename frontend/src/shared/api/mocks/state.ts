import type { components } from "../schema/generated";

type Schemas = components["schemas"];

// обработчику приходит express-запрос: кроме разобранных полей у него есть
// непрочитанный поток тела, из которого `multipart.ts` достаёт файл
export type MockHttpRequest = AsyncIterable<Uint8Array> & {
  params: Record<string, string>;
  query: Record<string, string | undefined>;
  body: Record<string, unknown>;
  headers: Record<string, string | undefined>;
};

type MockHouse = {
  id: number;
  region: string;
  city: string;
  street: string;
  building: string;
  is_connected: boolean;
  entrances: number;
  cadastral_no: string;
  built_year: number;
  floors: number;
  area: number;
  lat: number;
  lon: number;
  org: Schemas["OrgContacts"] | null;
};

type MockFlat = {
  id: number;
  house_id: number;
  number: string;
  entrance: number;
  area: number;
  account_no: string;
};

type MockVerification = {
  id: number;
  created_at: string;
  flat_id: number;
  account_no: string;
  comment: string | null;
  status: Schemas["VerificationStatus"];
  reason: string | null;
};

type MockRequest = {
  id: number;
  house_id: number;
  created_at: string;
  category: Schemas["RequestCategory"];
  description: string;
  status: Schemas["RequestStatus"];
  channel: Schemas["RequestChannel"];
  has_photos: boolean;
  group_size: number;
  group_id: number | null;
  flat_number: string | null;
  executor_name: string | null;
  rating: number | null;
  feedback: string | null;
  has_result_photos: boolean;
  deadline_at: string | null;
  parent_request_id: number | null;
  completion_reason: Schemas["RequestCompletionReason"] | null;
  photo_names: string[];
  messages: { after_minutes: number; text: string }[];
};

type MockMeter = {
  id: number;
  flat_id: number;
  type: Schemas["MeterType"];
  tariff_zones: number;
  serial: string;
  next_verification_date: string | null;
};

type MockReading = {
  id: number;
  meter_id: number;
  period: string;
  values: Record<string, number>;
  photos: string[];
  ocr_used: boolean;
  submitted_at: string;
};

type MockResidency = {
  resident_id: number;
  house_id: number;
  flat_id: number | null;
  flat_number: string | null;
  role: Schemas["ResidentRole"];
  verified: boolean;
};

const ZHILSERVIS: Schemas["OrgContacts"] = {
  id: 1,
  name: "ООО «Жилсервис»",
  phone: "+7 843 200-10-10",
  address: "Казань, ул. Баумана, 10",
  license_no: "16-000123",
  reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
  is_demo: true,
};

// УК неподключённого дома известна из реестра лицензий, поэтому контакты у неё
// есть, а кабинета в сервисе - нет
const LENINSKIY: Schemas["OrgContacts"] = {
  id: 2,
  name: "ООО «УК Ленинская»",
  phone: "+7 843 200-40-40",
  address: "Казань, ул. Ленина, 2",
  license_no: "16-000456",
  reception_note: null,
  is_demo: false,
};

const HOUSES: MockHouse[] = [
  {
    id: 1,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "12",
    is_connected: true,
    entrances: 4,
    cadastral_no: "16:50:011725:128",
    built_year: 1987,
    floors: 9,
    area: 845012,
    lat: 55.7903,
    lon: 49.1221,
    org: ZHILSERVIS,
  },
  {
    id: 2,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "14",
    is_connected: true,
    entrances: 2,
    cadastral_no: "16:50:011725:131",
    built_year: 1992,
    floors: 5,
    area: 412300,
    lat: 55.7911,
    lon: 49.1229,
    org: ZHILSERVIS,
  },
  {
    id: 3,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "16",
    is_connected: true,
    entrances: 3,
    cadastral_no: "16:50:011725:140",
    built_year: 2004,
    floors: 12,
    area: 690455,
    lat: 55.7918,
    lon: 49.1235,
    org: ZHILSERVIS,
  },
  {
    id: 4,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Ленина",
    building: "4",
    is_connected: false,
    entrances: 2,
    cadastral_no: "16:50:011802:44",
    built_year: 1975,
    floors: 5,
    area: 310800,
    lat: 55.7841,
    lon: 49.1103,
    org: LENINSKIY,
  },
];

const FLATS: MockFlat[] = [
  {
    id: 101,
    house_id: 1,
    number: "45",
    entrance: 2,
    area: 5420,
    account_no: "1600450012",
  },
  {
    id: 102,
    house_id: 1,
    number: "112",
    entrance: 4,
    area: 7310,
    account_no: "1601120034",
  },
  {
    id: 103,
    house_id: 1,
    number: "7",
    entrance: 1,
    area: 3890,
    account_no: "1600070055",
  },
  {
    id: 104,
    house_id: 2,
    number: "3",
    entrance: 1,
    area: 4210,
    account_no: "1400030077",
  },
];

const period = (monthsBack: number): string => {
  const today = new Date();
  const month = new Date(today.getFullYear(), today.getMonth() - monthsBack, 1);

  return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-01`;
};

const METERS: MockMeter[] = [
  {
    id: 201,
    flat_id: 101,
    type: "electricity",
    tariff_zones: 2,
    serial: "E-88214",
    next_verification_date: "2029-04-01",
  },
  {
    id: 202,
    flat_id: 101,
    type: "cold_water",
    tariff_zones: 1,
    serial: "CW-10432",
    next_verification_date: "2027-11-01",
  },
  {
    id: 203,
    flat_id: 101,
    type: "hot_water",
    tariff_zones: 1,
    serial: "HW-22881",
    next_verification_date: "2027-11-01",
  },
];

// показания прошлого месяца: с ними у формы есть «прошлое значение», а у
// отправленного показания - расход
const SEED_READINGS: MockReading[] = [
  {
    id: 3001,
    meter_id: 201,
    period: period(1),
    values: { day: 12310000, night: 4150000 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
  {
    id: 3002,
    meter_id: 202,
    period: period(1),
    values: { single: 214300 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
  {
    id: 3003,
    meter_id: 203,
    period: period(1),
    values: { single: 118900 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
];

// копия CATEGORY_RULES бэка: справочник категорий отдаёт те же подписи,
// зоны и нормативы
const CATEGORY_RULES: Record<
  Schemas["RequestCategory"],
  { label: string; zone: Schemas["ResponsibilityZone"]; hours: number }
> = {
  leak: { label: "Протечка", zone: "management", hours: 4 },
  elevator: { label: "Лифт", zone: "management", hours: 24 },
  garbage: { label: "Мусор", zone: "management", hours: 24 },
  heating: { label: "Отопление", zone: "utility", hours: 24 },
  water_supply: { label: "Водоснабжение", zone: "utility", hours: 8 },
  electricity: { label: "Электричество", zone: "utility", hours: 24 },
  entrance: { label: "Подъезд", zone: "management", hours: 72 },
  yard: { label: "Двор и территория", zone: "municipality", hours: 72 },
  meter_error: { label: "Ошибка в показаниях", zone: "management", hours: 72 },
  charge_dispute: {
    label: "Спор по начислению",
    zone: "management",
    hours: 72,
  },
  other: { label: "Другое", zone: "management", hours: 72 },
};

const minutes = (count: number) =>
  new Date(Date.now() + count * 60 * 1000).toISOString();

const days = (count: number) => minutes(count * 24 * 60);

const request = (
  fields: Pick<
    MockRequest,
    "id" | "category" | "description" | "status" | "created_at"
  > &
    Partial<MockRequest>,
): MockRequest => {
  const item: MockRequest = {
    house_id: 1,
    channel: "miniapp",
    has_photos: true,
    group_size: 1,
    group_id: null,
    flat_number: "45",
    executor_name: null,
    rating: null,
    feedback: null,
    has_result_photos: false,
    deadline_at: null,
    parent_request_id: null,
    completion_reason: null,
    photo_names: [],
    messages: [],
    ...fields,
  };

  // у завершённой заявки причина есть всегда; демо-данные называют её только
  // там, где она не «житель принял»
  if (item.status === "done" && item.completion_reason === null) {
    item.completion_reason = "resident_accepted";
  }

  return item;
};

// демо-лента повторяет макет; сроки считаются от «сейчас», иначе заявки
// протухают вместе с датой, на которую их написали
const SEED_REQUESTS: MockRequest[] = [
  request({
    id: 145,
    category: "water_supply",
    description: "Нет холодной воды",
    status: "accepted",
    created_at: days(-2),
    deadline_at: minutes(20 * 60),
    messages: [
      {
        after_minutes: 26,
        text: "Авария на водоводе, работы ведёт Водоканал. Передали вашу заявку, следим за сроками.",
      },
    ],
  }),
  request({
    id: 142,
    category: "leak",
    description: "Протечка, 2-й подъезд",
    status: "in_progress",
    created_at: days(-3),
    deadline_at: minutes(332),
    group_size: 7,
    group_id: 12,
    executor_name: "Сантехник Алексей Петров",
    messages: [
      {
        after_minutes: 18,
        text: "Заявку приняли, передаём сантехнику. Напишем, когда назначим время.",
      },
      {
        after_minutes: 104,
        text: "Сантехник придёт сегодня до 16:00. Обеспечьте, пожалуйста, доступ в квартиру.",
      },
    ],
  }),
  request({
    id: 141,
    category: "electricity",
    description: "Снова не горит свет на 5 этаже",
    status: "in_progress",
    created_at: days(-1),
    deadline_at: minutes(10 * 60),
    parent_request_id: 131,
  }),
  request({
    id: 139,
    category: "heating",
    description: "Холодные батареи в квартире",
    status: "in_progress",
    created_at: days(-5),
    deadline_at: minutes(-190),
  }),
  request({
    id: 137,
    category: "elevator",
    description: "Не закрывается дверь лифта",
    status: "on_review",
    // приёмка должна идти прямо сейчас: от шага «На приёмке» считается
    // автозакрытие, и с давней датой счётчик показывал бы прошедшее
    created_at: days(-2),
    deadline_at: days(-1),
    executor_name: "Механик Ильдар Гафуров",
    has_result_photos: true,
    messages: [
      {
        after_minutes: 1330,
        text: "Заменили доводчик двери. Посмотрите, пожалуйста, и примите работу.",
      },
    ],
  }),
  request({
    id: 133,
    category: "garbage",
    description: "Не вывезли мусор с площадки",
    status: "new",
    created_at: minutes(-120),
    deadline_at: minutes(22 * 60),
    has_photos: false,
  }),
  request({
    id: 131,
    category: "electricity",
    description: "Не горит свет на 5 этаже",
    status: "done",
    created_at: days(-16),
    executor_name: "Электрик Олег Смирнов",
    messages: [
      {
        after_minutes: 1425,
        text: "Заменили лампу и датчик движения на 5 этаже.",
      },
    ],
  }),
  request({
    id: 128,
    category: "entrance",
    description: "Разбито стекло в подъезде",
    status: "done",
    created_at: days(-20),
    // житель до приёмки не дошёл: такую заявку оценить уже нельзя
    completion_reason: "auto_closed",
  }),
  request({
    id: 126,
    category: "yard",
    description: "Яма у детской площадки",
    status: "done",
    created_at: days(-24),
    rating: 4,
    feedback: "Засыпали быстро, но асфальт положили не везде.",
  }),
  request({
    id: 120,
    category: "garbage",
    description: "Мусор у контейнерной площадки",
    status: "done",
    created_at: days(-28),
    rating: 5,
  }),
  request({
    id: 118,
    category: "meter_error",
    description: "Ошибка в показаниях за июль",
    status: "done",
    created_at: days(-33),
    rating: 4,
    has_photos: false,
  }),
  request({
    id: 112,
    category: "charge_dispute",
    description: "Спор по начислению за отопление",
    status: "done",
    created_at: days(-40),
    rating: 5,
    has_photos: false,
  }),
  request({
    id: 108,
    category: "other",
    description: "Не работает домофон у первого подъезда",
    status: "done",
    created_at: days(-46),
    rating: 5,
  }),
];

const TAKEN_FLAT_IDS = new Set<number>([103]);

const state = {
  user: {
    user_id: 1,
    name: "Тестовый Житель",
    consent_at: null as string | null,
    consent_version: null as string | null,
  },
  residencies: [] as MockResidency[],
  verifications: [] as MockVerification[],
  demand: new Map<number, number>([[4, 11]]),
  demandSent: new Set<number>(),
  requests: [...SEED_REQUESTS],
  readings: [...SEED_READINGS],
  files: new Map<string, string>(),
  nextResidentId: 501,
  nextVerificationId: 9001,
  nextRequestId: 150,
  nextReadingId: 3100,
  nextFileId: 1,
};

export const resetState = (): void => {
  state.user.consent_at = null;
  state.user.consent_version = null;
  state.residencies = [];
  state.verifications = [];
  state.demand = new Map([[4, 11]]);
  state.demandSent = new Set();
  state.requests = [...SEED_REQUESTS];
  state.readings = [...SEED_READINGS];
  state.files = new Map();
  state.nextResidentId = 501;
  state.nextVerificationId = 9001;
  state.nextRequestId = 150;
  state.nextReadingId = 3100;
  state.nextFileId = 1;
};

export const hasConsent = (): boolean => state.user.consent_at !== null;

export const acceptConsent = (version: string): void => {
  state.user.consent_at = new Date().toISOString();
  state.user.consent_version = version;
};

export const findHouse = (houseId: number): MockHouse | undefined =>
  HOUSES.find((house) => house.id === houseId);

const normalize = (value: string): string =>
  value.trim().toLowerCase().replace(/\s+/g, " ");

export const searchHouses = (query: string): MockHouse[] => {
  const words = normalize(query).split(" ").filter(Boolean);

  if (words.length === 0) {
    return [];
  }

  return HOUSES.filter((house) => {
    const address = normalize(
      `${house.city} ${house.street} ${house.building}`,
    );

    return words.every((word) => address.includes(word));
  });
};

export const houseFlats = (houseId: number, query: string): MockFlat[] => {
  const normalized = normalize(query);
  const flats = FLATS.filter((flat) => flat.house_id === houseId);

  if (!normalized) {
    return flats;
  }

  return flats.filter((flat) => flat.number.toLowerCase() === normalized);
};

export const findFlat = (flatId: number): MockFlat | undefined =>
  FLATS.find((flat) => flat.id === flatId);

export const residencies = (): MockResidency[] => state.residencies;

export const residencyForHouse = (houseId: number): MockResidency | undefined =>
  state.residencies.find((residency) => residency.house_id === houseId);

export const addResidency = (
  houseId: number,
  flat: MockFlat | null,
  flatNumber: string | null,
  role: Schemas["ResidentRole"],
): MockResidency => {
  const existing = residencyForHouse(houseId);

  if (existing) {
    return existing;
  }

  const residency: MockResidency = {
    resident_id: state.nextResidentId,
    house_id: houseId,
    flat_id: flat?.id ?? null,
    flat_number: flat?.number ?? flatNumber,
    role,
    verified: false,
  };
  state.nextResidentId += 1;
  state.residencies.push(residency);

  return residency;
};

export const latestVerification = (
  flatId: number,
): MockVerification | undefined =>
  state.verifications.findLast((request) => request.flat_id === flatId);

export const addVerification = (
  flatId: number,
  accountNo: string,
  comment: string | null,
  status: Schemas["VerificationStatus"],
  reason: string | null,
): MockVerification => {
  const request: MockVerification = {
    id: state.nextVerificationId,
    created_at: new Date().toISOString(),
    flat_id: flatId,
    account_no: accountNo,
    comment,
    status,
    reason,
  };
  state.nextVerificationId += 1;
  state.verifications.push(request);

  return request;
};

// подтверждение и есть тот момент, когда у привязки появляется квартира:
// до него житель мог указать ее свободным номером
export const setVerified = (residency: MockResidency, flatId: number): void => {
  residency.verified = true;
  residency.flat_id = flatId;
};

export const signalDemand = (houseId: number): number => {
  if (state.demandSent.has(houseId)) {
    return demandTotal(houseId);
  }

  const total = (state.demand.get(houseId) ?? 0) + 1;
  state.demand.set(houseId, total);
  state.demandSent.add(houseId);

  return total;
};

export const demandTotal = (houseId: number): number =>
  state.demand.get(houseId) ?? 0;

export const houseRequests = (
  houseId: number,
  status: Schemas["RequestStatus"] | null,
): MockRequest[] =>
  state.requests
    .filter(
      (item) =>
        item.house_id === houseId &&
        (status === null || item.status === status),
    )
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

export const requestListItem = (
  item: MockRequest,
): Schemas["RequestListItem"] => ({
  id: item.id,
  created_at: item.created_at,
  category: item.category,
  category_label: CATEGORY_RULES[item.category].label,
  description: item.description,
  status: item.status,
  channel: item.channel,
  has_photos: item.has_photos,
  group_size: item.group_size,
  flat_number: item.flat_number,
  group_id: item.group_id,
  executor_name: item.executor_name,
  rating: item.rating,
  deadline_at: item.deadline_at,
  completion_reason: item.completion_reason,
});

// заявка держит только случившееся; шаг помечается ролью того, кто его сделал
const STEP: {
  status: Schemas["RequestStatus"];
  after_minutes: number;
  by_role: string;
}[] = [
  { status: "new", after_minutes: 0, by_role: "resident" },
  { status: "accepted", after_minutes: 17, by_role: "staff" },
  { status: "in_progress", after_minutes: 102, by_role: "staff" },
  { status: "on_review", after_minutes: 1320, by_role: "executor" },
  { status: "done", after_minutes: 1440, by_role: "resident" },
];

const shift = (iso: string, addMinutes: number) =>
  new Date(new Date(iso).getTime() + addMinutes * 60 * 1000).toISOString();

const requestTimeline = (
  item: MockRequest,
): Schemas["RequestStatusLogItem"][] => {
  const reached = STEP.findIndex(({ status }) => status === item.status);

  return STEP.slice(0, reached + 1).map((step, index) => ({
    at: shift(item.created_at, step.after_minutes),
    to_status: step.status,
    by_role:
      step.status === "done" && item.completion_reason === "auto_closed"
        ? "system"
        : step.by_role,
    from_status: index === 0 ? null : STEP[index - 1].status,
  }));
};

// бэковая AUTO_CLOSE_AFTER: момент автозакрытия считает бэк, мок стоит на
// его месте и считает так же - от шага «На приёмке»
const autoCloseAt = (item: MockRequest): string | null => {
  if (item.status !== "on_review") {
    return null;
  }

  const sent = requestTimeline(item).find(
    (entry) => entry.to_status === "on_review",
  );

  return sent ? shift(sent.at, 48 * 60) : null;
};

const RESULT_PHOTO: Schemas["FileRef"] = {
  name: "Фото исполнителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23c7d4e0'/%3E%3C/svg%3E",
};

const PHOTO: Schemas["FileRef"] = {
  name: "Фото от жителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23d9d9d9'/%3E%3C/svg%3E",
};

// загруженные фото приезжают по именам, демо-заявки обходятся заглушкой
const requestPhotos = (item: MockRequest): Schemas["FileRef"][] => {
  if (item.photo_names.length > 0) {
    return item.photo_names.map((name) => ({
      name,
      url: state.files.get(name) ?? PHOTO.url,
    }));
  }

  return item.has_photos ? [PHOTO] : [];
};

export const requestCard = (item: MockRequest): Schemas["RequestCard"] => {
  const house = findHouse(item.house_id);

  return {
    ...requestListItem(item),
    house_id: item.house_id,
    address: house ? address(house) : "",
    org_name: house?.org?.name ?? null,
    normative_hours: CATEGORY_RULES[item.category].hours,
    photos: requestPhotos(item),
    result_photos: item.has_result_photos ? [RESULT_PHOTO] : [],
    messages: item.messages.map((message) => ({
      created_at: shift(item.created_at, message.after_minutes),
      author_role: "staff",
      author_name: "Диспетчер УК",
      text: message.text,
    })),
    timeline: requestTimeline(item),
    can_review: item.status === "on_review",
    can_rate:
      item.completion_reason === "resident_accepted" && item.rating === null,
    feedback: item.feedback,
    parent_request_id: item.parent_request_id,
    flat_id: residencyForHouse(item.house_id)?.flat_id ?? null,
    auto_close_at: autoCloseAt(item),
  };
};

export const findRequest = (requestId: number): MockRequest | undefined =>
  state.requests.find((item) => item.id === requestId);

// приёмка закрывает заявку в обе стороны; отказ отличается причиной, по
// которой заявку потом нельзя оценить
export const acceptRequest = (item: MockRequest): MockRequest => {
  item.status = "done";
  item.completion_reason = "resident_accepted";

  return item;
};

export const rejectRequest = (item: MockRequest): MockRequest => {
  item.status = "done";
  item.completion_reason = "resident_rejected";

  return item;
};

export const rateRequest = (
  item: MockRequest,
  rating: number,
  feedback: string | null,
): MockRequest => {
  item.rating = rating;
  item.feedback = feedback;

  return item;
};

// демо-соседи: у протечки уже собрана группа, к отоплению присоединиться
// нельзя - окно склейки закрыто, но пожаловавшиеся соседи есть
const NEIGHBOURS: Partial<Record<Schemas["RequestCategory"], number>> = {
  heating: 3,
  elevator: 1,
};

export const similarRequests = (
  houseId: number,
  category: Schemas["RequestCategory"],
): Schemas["SimilarRequestsResponse"] => {
  const group = state.requests.find(
    (item) =>
      item.house_id === houseId &&
      item.category === category &&
      item.group_id !== null &&
      item.status !== "done",
  );

  if (group) {
    return {
      category,
      neighbours_count: group.group_size,
      can_join: true,
      group_id: group.group_id,
      window_started_at: group.created_at,
    };
  }

  return {
    category,
    neighbours_count: NEIGHBOURS[category] ?? 0,
    can_join: false,
    group_id: null,
    window_started_at: null,
  };
};

export const saveFile = (name: string, url: string): void => {
  state.files.set(name, url);
};

export const nextFileName = (): string => {
  const name = `photo-${state.nextFileId}.jpg`;
  state.nextFileId += 1;

  return name;
};

export const createRequest = (
  houseId: number,
  body: Schemas["CreateRequestRequest"],
): MockRequest => {
  const created = request({
    id: state.nextRequestId,
    house_id: houseId,
    category: body.category,
    description: body.description,
    status: "new",
    created_at: minutes(0),
    deadline_at: minutes(CATEGORY_RULES[body.category].hours * 60),
    flat_number: residencyForHouse(houseId)?.flat_number ?? null,
    group_id: body.join_group_id ?? null,
    has_photos: (body.photos?.length ?? 0) > 0,
    photo_names: body.photos ?? [],
  });
  state.nextRequestId += 1;
  state.requests.push(created);

  // присоединение растит группу: новое число квартир видят все её заявки
  if (created.group_id !== null) {
    const members = state.requests.filter(
      (item) => item.group_id === created.group_id && item.id !== created.id,
    );
    const size = (members[0]?.group_size ?? 0) + 1;

    [...members, created].forEach((item) => {
      item.group_size = size;
    });
  }

  return created;
};

// повтор наследует категорию и квартиру исходной заявки: житель жалуется на
// ту же проблему, а не заводит новую
export const repeatRequest = (
  item: MockRequest,
  description: string | null,
  photos: string[],
): MockRequest => {
  const created = request({
    id: state.nextRequestId,
    house_id: item.house_id,
    category: item.category,
    description: description?.trim() || `Повторно по заявке №${item.id}`,
    status: "new",
    created_at: minutes(0),
    deadline_at: minutes(CATEGORY_RULES[item.category].hours * 60),
    flat_number: item.flat_number,
    parent_request_id: item.id,
    has_photos: photos.length > 0,
    photo_names: photos,
  });
  state.nextRequestId += 1;
  state.requests.push(created);

  return created;
};

export const requestCategories = (): Schemas["RequestCategoryItem"][] =>
  Object.entries(CATEGORY_RULES).map(([category, rule]) => ({
    category: category as Schemas["RequestCategory"],
    label: rule.label,
    zone: rule.zone,
    normative_hours: rule.hours,
  }));

export const address = (house: MockHouse): string =>
  `${house.city}, ул. ${house.street}, д. ${house.building}`;

export const houseListItem = (house: MockHouse): Schemas["HouseListItem"] => ({
  id: house.id,
  address: address(house),
  city: `${house.city}, ${house.region}`,
  street: house.street,
  building: house.building,
  is_connected: house.is_connected,
  org_name: house.org?.name ?? null,
  distance_m: null,
});

export const houseCard = (house: MockHouse): Schemas["HouseCard"] => ({
  id: house.id,
  address: address(house),
  region: house.region,
  city: house.city,
  street: house.street,
  building: house.building,
  cadastral_no: house.cadastral_no,
  entrances: house.entrances,
  is_connected: house.is_connected,
  demand_count: demandTotal(house.id),
  demand_sent: state.demandSent.has(house.id),
  built_year: house.built_year,
  floors: house.floors,
  area: house.area,
  lat: house.lat,
  lon: house.lon,
  org: house.org,
  my_residency: (() => {
    const residency = residencyForHouse(house.id);

    return residency ? residencySummary(residency) : null;
  })(),
  chat_binding_code: null,
  chat_bound: false,
  overhaul: null,
  documents: [],
});

export const flatListItem = (flat: MockFlat): Schemas["FlatListItem"] => ({
  id: flat.id,
  number: flat.number,
  entrance: flat.entrance,
  area: flat.area,
  is_taken: TAKEN_FLAT_IDS.has(flat.id),
});

export const flatCard = (
  flat: MockFlat,
  residency: MockResidency,
): Schemas["FlatCard"] => {
  const house = findHouse(flat.house_id);
  const canSeeCharges = residency.role === "owner";

  return {
    id: flat.id,
    house_id: flat.house_id,
    address: house ? address(house) : "",
    number: flat.number,
    role: residency.role,
    verified: residency.verified,
    can_see_charges: canSeeCharges,
    can_vote: canSeeCharges,
    meters_count: flatMeters(flat.id).length,
    residents_count: state.residencies.filter(
      (item) => item.flat_id === flat.id,
    ).length,
    entrance: flat.entrance,
    area: flat.area,
    // хвост лицевого счета видит только подтвержденный житель с доступом к
    // начислениям: арендатору счет не показывают вовсе
    account_no:
      residency.verified && canSeeCharges ? flat.account_no.slice(-4) : null,
    verification_status: latestVerification(flat.id)?.status ?? null,
  };
};

export const removeResidency = (residentId: number): boolean => {
  const next = state.residencies.filter(
    (residency) => residency.resident_id !== residentId,
  );

  if (next.length === state.residencies.length) {
    return false;
  }

  state.residencies = next;

  return true;
};

export function residencySummary(
  residency: MockResidency,
): Schemas["ResidencySummary"] {
  const house = findHouse(residency.house_id);
  const latest =
    residency.flat_id === null
      ? undefined
      : latestVerification(residency.flat_id);

  return {
    resident_id: residency.resident_id,
    house_id: residency.house_id,
    address: house ? address(house) : "",
    role: residency.role,
    status: "active",
    verified: residency.verified,
    is_chairman: false,
    can_see_charges: residency.role === "owner",
    can_vote: residency.role === "owner",
    is_connected: house?.is_connected ?? false,
    flat_id: residency.flat_id,
    flat_number: residency.flat_number,
    verification_status: latest?.status ?? null,
    // причина принадлежит отказу: у одобренного запроса в этом поле заметка УК
    verification_reject_reason:
      latest?.status === "rejected" ? latest.reason : null,
  };
}

export const verificationRequestItem = (
  request: MockVerification,
  flat: MockFlat,
): Schemas["VerificationRequestItem"] => {
  const house = findHouse(flat.house_id);

  return {
    id: request.id,
    created_at: request.created_at,
    flat_id: flat.id,
    flat_number: flat.number,
    house_id: flat.house_id,
    address: house ? address(house) : "",
    user_id: state.user.user_id,
    user_name: state.user.name,
    account_no: request.account_no,
    status: request.status,
    comment: request.comment,
    reason: request.reason,
  };
};

export const me = (): Schemas["MeResponse"] => ({
  user_id: state.user.user_id,
  name: state.user.name,
  consent_at: state.user.consent_at,
  consent_version: state.user.consent_version,
  residencies: state.residencies.map(residencySummary),
  orgs: [],
  is_demo: true,
});

// тариф в 1/10000 рубля за единицу, как в справочнике тарифов бэка
const METER_TARIFF: Record<Schemas["MeterType"], number> = {
  electricity: 56000,
  cold_water: 350000,
  hot_water: 2100000,
  gas: 78000,
  heating: 21000000,
};

// среднее по дому считать не из чего: в моке счётчики есть только у одной
// квартиры, поэтому расход соседей задан демо-значением
const HOUSE_AVERAGE: Record<Schemas["MeterType"], number> = {
  electricity: 210000,
  cold_water: 4200,
  hot_water: 3100,
  gas: 5400,
  heating: 140,
};

// сколько прибавляет к прошлому показанию «распознавание» фото
const OCR_STEP: Record<Schemas["MeterType"], number> = {
  electricity: 148000,
  cold_water: 4300,
  hot_water: 3400,
  gas: 5200,
  heating: 120,
};

const today = (): string => new Date().toISOString().slice(0, 10);

export const currentPeriod = (): string => period(0);

export const flatMeters = (flatId: number): MockMeter[] =>
  METERS.filter((meter) => meter.flat_id === flatId);

export const findMeter = (meterId: number): MockMeter | undefined =>
  METERS.find((meter) => meter.id === meterId);

const meterReadings = (meterId: number): MockReading[] =>
  state.readings
    .filter((reading) => reading.meter_id === meterId)
    .sort(
      (a, b) =>
        b.period.localeCompare(a.period) ||
        b.submitted_at.localeCompare(a.submitted_at),
    );

export const meterItem = (meter: MockMeter): Schemas["MeterItem"] => {
  const last = meterReadings(meter.id).at(0);
  const expired =
    meter.next_verification_date !== null &&
    meter.next_verification_date < today();

  return {
    id: meter.id,
    flat_id: meter.flat_id,
    type: meter.type,
    tariff_zones: meter.tariff_zones,
    serial: meter.serial,
    can_submit: !expired,
    verification_expired: expired,
    next_verification_date: meter.next_verification_date,
    last_period: last?.period ?? null,
    last_values: last?.values ?? null,
  };
};

export const readingPeriods = (
  flatId: number,
): Schemas["ReadingPeriodItem"][] => {
  const current = currentPeriod();

  return [
    {
      period: current,
      is_open: true,
      is_submitted: flatMeters(flatId).some((meter) =>
        meterReadings(meter.id).some((reading) => reading.period === current),
      ),
    },
  ];
};

const previousValues = (
  meterId: number,
  before: string,
): Record<string, number> | null =>
  meterReadings(meterId).find((reading) => reading.period < before)?.values ??
  null;

const consumptionOf = (
  values: Record<string, number>,
  previous: Record<string, number> | null,
): Record<string, number> =>
  Object.fromEntries(
    Object.entries(values).map(([zone, value]) => [
      zone,
      // первая подача расхода не даёт: считать его от нуля значит выставить
      // жителю весь ресурс, прошедший через счётчик за всю его жизнь
      previous === null ? 0 : value - (previous[zone] ?? value),
    ]),
  );

// тысячные объёма * тариф (1/10000 рубля) даёт 1/100000 копейки
const kopecks = (consumption: Record<string, number>, tariff: number): number =>
  Math.floor(
    (Object.values(consumption).reduce(
      (sum, value) => sum + value * tariff,
      0,
    ) +
      50000) /
      100000,
  );

export const readingItem = (
  reading: MockReading,
  meter: MockMeter,
): Schemas["ReadingItem"] => {
  const previous = previousValues(meter.id, reading.period);
  const consumption = consumptionOf(reading.values, previous);

  return {
    id: reading.id,
    meter_id: reading.meter_id,
    period: reading.period,
    values: reading.values,
    consumption,
    photos: reading.photos.map((name) => ({
      name,
      url: state.files.get(name) ?? "",
    })),
    is_below_previous:
      previous !== null &&
      Object.entries(reading.values).some(
        ([zone, value]) => value < (previous[zone] ?? value),
      ),
    ocr_used: reading.ocr_used,
    submitted_at: reading.submitted_at,
    amount: kopecks(consumption, METER_TARIFF[meter.type]),
  };
};

export const meterHistory = (meter: MockMeter): Schemas["ReadingItem"][] =>
  meterReadings(meter.id).map((reading) => readingItem(reading, meter));

export const submitReading = (
  meter: MockMeter,
  body: Schemas["SubmitReadingRequest"],
): MockReading => {
  const created: MockReading = {
    id: state.nextReadingId,
    meter_id: meter.id,
    period: body.period,
    values: body.values,
    photos: body.photos ?? [],
    ocr_used: body.ocr_used,
    submitted_at: new Date().toISOString(),
  };

  state.nextReadingId += 1;
  state.readings = [created, ...state.readings];

  return created;
};

export const houseAverage = (meter: MockMeter): number =>
  HOUSE_AVERAGE[meter.type];

export const recognizedValues = (
  meterType: Schemas["MeterType"],
): Record<string, number> | null => {
  const meter = METERS.find((item) => item.type === meterType);

  if (!meter) {
    return null;
  }

  const last = meterReadings(meter.id).at(0);

  if (!last) {
    return null;
  }

  const step = OCR_STEP[meterType];

  return Object.fromEntries(
    Object.entries(last.values).map(([zone, value]) => [
      zone,
      // ночью в квартире тратят меньше, чем днём - демо-прирост это повторяет
      value + (zone === "night" ? Math.round(step / 3000) * 1000 : step),
    ]),
  );
};
