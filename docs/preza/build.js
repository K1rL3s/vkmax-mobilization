const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const lu = require("react-icons/lu");
const JSZip = require("jszip");

const AVATAR = path.join(__dirname, "..", "zheka.png");
const OUT = process.argv[2] || path.join(__dirname, "zheka.pptx");
const ASSETS = path.join(__dirname, "build", "assets");

const C = {
  sky: "359CFC", blue: "1E7CF8", deep: "0958DF", navy: "173267", night: "0A1A3E",
  vest: "FE781A", refl: "D5D9E6", stripe: "0548AB", white: "F7F9FC", pure: "FFFFFF",
  done: "2EB872", alert: "E5484D", muted: "5A6B8C",
};
const TEAM = [
  ["Кирилл Лесовой", "капитан, бэкенд"],
  ["Даниил Карпенко", "фронтенд"],
  ["Даниил Неслуховский", "аналитик"],
  ["Артаган Мальсагов", "бэкенд"],
];
const BOT = "https://max.ru/t260_hakaton_max_bot";
let CLEAR_PNG;
const H = "Unbounded";
const B = "Manrope";
const W = 13.333;
const SH = 7.5;

async function gradient(file, stops) {
  const s = stops.map(([o, c]) => `<stop offset="${o}" stop-color="#${c}"/>`).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">${s}</linearGradient></defs><rect width="1920" height="1080" fill="url(#g)"/></svg>`;
  await sharp(Buffer.from(svg)).png().toFile(file);
}

async function buildAssets() {
  fs.mkdirSync(ASSETS, { recursive: true });
  const clear = await sharp({ create: { width: 1, height: 1, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } }).png().toBuffer();
  CLEAR_PNG = `image/png;base64,${clear.toString("base64")}`;
  await gradient(`${ASSETS}/bg-main.png`, [[0, C.sky], [0.5, C.blue], [1, C.deep]]);
  await gradient(`${ASSETS}/bg-deep.png`, [[0, C.deep], [1, C.navy]]);

  const size = 1254;
  const fade = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><defs><linearGradient id="f" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.28" stop-color="#fff" stop-opacity="1"/></linearGradient><linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.12" stop-color="#fff" stop-opacity="1"/></linearGradient><mask id="m"><rect width="${size}" height="${size}" fill="url(#t)"/></mask></defs><rect width="${size}" height="${size}" fill="url(#f)" mask="url(#m)"/></svg>`;
  await sharp(AVATAR).ensureAlpha()
    .composite([{ input: Buffer.from(fade), blend: "dest-in" }])
    .png().toFile(`${ASSETS}/zheka-fade.png`);

  const d = 600;
  const ring = `<svg xmlns="http://www.w3.org/2000/svg" width="${d}" height="${d}"><circle cx="${d / 2}" cy="${d / 2}" r="${d / 2 - 9}" fill="none" stroke="#${C.night}" stroke-width="18"/></svg>`;
  const disc = `<svg xmlns="http://www.w3.org/2000/svg" width="${d}" height="${d}"><circle cx="${d / 2}" cy="${d / 2}" r="${d / 2}" fill="#fff"/></svg>`;
  const crop = await sharp(AVATAR).extract({ left: 200, top: 30, width: 900, height: 900 }).resize(d, d).png().toBuffer();
  await sharp(crop).ensureAlpha()
    .composite([{ input: Buffer.from(disc), blend: "dest-in" }, { input: Buffer.from(ring) }])
    .png().toFile(`${ASSETS}/zheka-circle.png`);

  const rows = [];
  for (let y = 0; y < 400; y += 16) rows.push(`<rect y="${y + 10}" width="400" height="6" fill="#${C.stripe}"/>`);
  const tel = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#${C.white}"/>${rows.join("")}</svg>`;
  await sharp(Buffer.from(tel)).png().toFile(`${ASSETS}/telnyashka.png`);
}

const iconCache = {};
async function icon(name, color) {
  const key = `${name}-${color}`;
  if (!iconCache[key]) {
    if (!lu[name]) throw new Error(`no icon ${name}`);
    const svg = renderToStaticMarkup(React.createElement(lu[name], { size: 256, color: `#${color}`, strokeWidth: 2 }));
    const buf = await sharp(Buffer.from(svg)).png().toBuffer();
    iconCache[key] = `image/png;base64,${buf.toString("base64")}`;
  }
  return iconCache[key];
}

let pres;

function text(slide, value, o) {
  slide.addText(value, { isTextBox: true, fontFace: B, color: C.navy, fontSize: 15, margin: 0, valign: "top", paraSpaceAfter: 0, ...o });
}

function title(slide, value, o = {}) {
  text(slide, value, { x: 0.6, y: 0.45, w: 11.4, h: 1.0, fontFace: H, bold: true, fontSize: 28, valign: "middle", ...o });
}

function card(slide, x, y, w, h, o = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: o.r ?? 0.2,
    fill: { color: o.fill || C.pure },
    line: o.noLine ? { type: "none" } : { color: o.line || C.night, width: o.lw ?? 1.5 },
    shadow: o.flat ? undefined : { type: "outer", blur: 0, offset: 3, angle: 90, color: C.night, opacity: 1 },
  });
}

async function badge(slide, name, x, y, d, o = {}) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: d, h: d,
    fill: { color: o.fill || C.pure },
    line: { color: o.line || C.night, width: 1.5 },
  });
  const inset = d * 0.24;
  slide.addImage({ data: await icon(name, o.color || C.navy), x: x + inset, y: y + inset, w: d - 2 * inset, h: d - 2 * inset });
}

function avatar(slide, x, y, d) {
  slide.addImage({ path: `${ASSETS}/zheka-circle.png`, x, y, w: d, h: d });
}

function says(slide, value, x, y, w, h, d, o = {}) {
  const right = o.side !== "left";
  const gap = 0.27;
  const adj1 = Math.round(((w / 2 + gap - 0.02) / w) * 100000) * (right ? 1 : -1);
  const adj2 = 20000;
  slide.addShape(pres.shapes.ROUNDED_RECTANGULAR_CALLOUT, {
    objectName: `says:${adj1}:${adj2}`,
    x, y, w, h,
    fill: { color: C.pure }, line: { color: C.night, width: 1.5 },
  });
  text(slide, value, { x: x + 0.16, y: y + 0.06, w: w - 0.32, h: h - 0.12, bold: true, fontSize: o.fontSize || 14, valign: "middle", align: "left" });
  const cy = y + h / 2 + (adj2 / 100000) * h;
  avatar(slide, right ? x + w + gap : x - gap - d, cy - d / 2, d);
}

async function aimBubbles(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const slides = Object.keys(zip.files).filter((f) => /^ppt\/slides\/slide\d+\.xml$/.test(f));
  for (const f of slides) {
    const xml = await zip.file(f).async("string");
    const aimed = xml.replace(
      /(name="says:(-?\d+):(-?\d+)"[\s\S]*?<a:prstGeom prst="wedgeRoundRectCallout">)\s*<a:avLst\s*(?:\/>|><\/a:avLst>)/g,
      '$1<a:avLst><a:gd name="adj1" fmla="val $2"/><a:gd name="adj2" fmla="val $3"/><a:gd name="adj3" fmla="val 16667"/></a:avLst>',
    );
    zip.file(f, aimed);
  }
  return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
}

function link(slide, url, x, y, w, h) {
  slide.addImage({ data: CLEAR_PNG, x, y, w, h, hyperlink: { url } });
}

function corner(slide) {
  slide.addImage({ path: `${ASSETS}/telnyashka.png`, x: W - 0.5, y: 0, w: 0.5, h: 0.5 });
}

function number(slide, n, light) {
  text(slide, String(n), { x: W - 1.1, y: SH - 0.5, w: 0.6, h: 0.3, fontSize: 10, align: "right", color: light ? C.pure : C.muted });
}

function lightSlide(n) {
  const s = pres.addSlide();
  s.background = { color: C.white };
  corner(s);
  number(s, n);
  return s;
}

function darkSlide(n, bg = "bg-deep.png") {
  const s = pres.addSlide();
  s.background = { path: `${ASSETS}/${bg}` };
  number(s, n, true);
  return s;
}

function bullets(items, o = {}) {
  return items.map((t, i) => ({
    text: t,
    options: { bullet: { indent: 16 }, breakLine: i < items.length - 1, paraSpaceAfter: o.gap ?? 6 },
  }));
}

function placeholder(slide, value, x, y, w, h) {
  slide.addText(value, {
    shape: pres.shapes.ROUNDED_RECTANGLE, isTextBox: true, x, y, w, h, rectRadius: 0.12,
    fill: { color: C.refl }, line: { color: C.muted, width: 1, dashType: "dash" },
    fontFace: B, fontSize: 12, color: C.navy, align: "center", valign: "middle", margin: 8,
  });
}

function phone(slide, file, x, y, h) {
  const pad = 0.1;
  const sh = h - 2 * pad;
  const sw = sh * (780 / 1688);
  const w = sw + 2 * pad;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.22, fill: { color: C.night }, line: { color: C.night, width: 1 },
    shadow: { type: "outer", blur: 0, offset: 3, angle: 90, color: C.stripe, opacity: 1 },
  });
  slide.addImage({ path: path.join(__dirname, "screens", file), x: x + pad, y: y + pad, w: sw, h: sh });
  return w;
}

async function build() {
  await buildAssets();
  pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "Жэка Коммуналкин";
  pres.company = "Команда «Мобилизация»";

  let n = 0;

  {
    const s = lightSlide(++n);
    title(s, "Для технической проверки");
    text(s, "Служебный слайд: ссылки, доступы и порядок проверки", { x: 0.6, y: 1.35, w: 9, h: 0.4, fontSize: 14, color: C.muted });

    card(s, 0.6, 2.0, 6.0, 4.9);
    text(s, "Ссылки", { x: 0.9, y: 2.2, w: 5.4, h: 0.4, fontFace: H, bold: true, fontSize: 16 });
    const kv = [
      ["Бот в MAX", "max.ru/t260_hakaton_max_bot", BOT],
      ["Репозиторий", "github.com/K1rL3s/vkmax-mobilization", "https://github.com/K1rL3s/vkmax-mobilization"],
      ["Commit", process.env.COMMIT || "[hash сдаваемой версии]"],
      ["API", "vkmax.k1rles.ru/api", "https://vkmax.k1rles.ru/api/healthcheck"],
      ["Документация", "vkmax.k1rles.ru/api/docs", "https://vkmax.k1rles.ru/api/docs"],
      ["Контракт", "openapi.yaml, DATA-API.yaml"],
      ["Токен API", "Bearer 34c63235dea4b1fb95ce89a9f108fc18"],
      ["Логины", "не нужны, вход по аккаунту MAX"],
      ["Лицевые счета", "номер квартиры с нулями: 0000000012"],
      ["Окружение", ".env.example; без MAX_TOKEN локально все, кроме бота"],
    ];
    kv.forEach(([k, v, url], i) => {
      const y = 2.68 + i * 0.4;
      text(s, k, { x: 0.9, y, w: 1.7, h: 0.4, fontSize: 13, bold: true, valign: "middle" });
      text(s, [{ text: v, options: url ? { hyperlink: { url }, color: C.deep } : {} }], { x: 2.65, y, w: 3.8, h: 0.4, fontSize: ["Commit", "Токен API"].includes(k) ? 11 : 13, valign: "middle" });
    });

    card(s, 6.9, 2.0, 5.83, 4.9);
    text(s, "Демо-доступ", { x: 7.2, y: 2.2, w: 5.2, h: 0.4, fontFace: H, bold: true, fontSize: 16 });
    text(s, "Нажмите на роль: ссылка откроет бота в MAX, и он выдаст эту роль", { x: 7.2, y: 2.7, w: 5.3, h: 0.6, fontSize: 13 });
    const roles = [
      ["demo_resident_1", "житель: своя квартира, история за 6 месяцев"],
      ["demo_staff_1", "сотрудник УК: заявки, показания"],
      ["demo_admin_1", "админ УК: дома, команда, аналитика"],
    ];
    roles.forEach(([k, v], i) => {
      const y = 3.45 + i * 0.62;
      const url = `${BOT}?start=${k}`;
      s.addText(k, { color: C.pure, shape: pres.shapes.ROUNDED_RECTANGLE, isTextBox: true, x: 7.2, y, w: 2.1, h: 0.42, rectRadius: 0.21, fill: { color: C.deep }, fontFace: B, bold: true, fontSize: 12, align: "center", valign: "middle", margin: 0 });
      link(s, url, 7.2, y, 2.1, 0.42);
      text(s, v, { x: 9.45, y, w: 3.1, h: 0.42, fontSize: 12.5, valign: "middle" });
    });
    text(s, "Порядок проверки", { x: 7.2, y: 5.4, w: 5.2, h: 0.35, fontSize: 13, bold: true });
    text(s, "Житель: заявка с фото и подсказкой категории, показания по фото. Сотрудник: принять заявку, отправить на приёмку. Житель: уведомление, приёмка и оценка в чате. Подробно - README, «Сценарий проверки»", { x: 7.2, y: 5.78, w: 5.3, h: 0.95, fontSize: 12.5 });
    s.addNotes("Слайд не оценивается, но по нему жюри проверяет решение. Перед сдачей собрать с COMMIT, см. AGENTS.md. Все ссылки открыть в инкогнито");
  }

  {
    const s = pres.addSlide();
    ++n;
    s.background = { path: `${ASSETS}/bg-main.png` };
    s.addImage({ path: `${ASSETS}/zheka-fade.png`, x: W - SH, y: 0, w: SH, h: SH });
    avatar(s, 0.7, 0.7, 1.1);
    text(s, "Жэка", { x: 2.0, y: 0.72, w: 4, h: 0.62, fontFace: H, bold: true, fontSize: 32, color: C.pure, valign: "middle" });
    text(s, "Коммуналкин", { x: 2.0, y: 1.33, w: 4, h: 0.4, bold: true, fontSize: 18, color: C.pure, valign: "middle" });
    text(s, "Потекло, погасло, сломалось? Пишите Жэке", { x: 0.7, y: 2.3, w: 5.9, h: 1.6, fontFace: H, bold: true, fontSize: 30, color: C.pure, valign: "top" });
    text(s, "Бот и мини-приложение в MAX для жителей многоквартирных домов и их управляющих компаний", { x: 0.7, y: 4.0, w: 5.2, h: 0.9, fontSize: 17, color: C.pure });
    text(s, "Команда «Мобилизация» · Хакатон MAX, трек «Умный город», 2026", { x: 0.7, y: 5.2, w: 6.0, h: 0.3, fontSize: 12, color: C.pure });
    TEAM.forEach(([name, role], i) => {
      text(s, [
        { text: name, options: { bold: true, fontSize: 14, breakLine: true } },
        { text: role, options: { fontSize: 12 } },
      ], { x: 0.7 + (i % 2) * 2.85, y: 5.65 + Math.floor(i / 2) * 0.72, w: 2.75, h: 0.6, color: C.pure });
    });
    s.addNotes("Название, слоган и состав команды с ролями: критерий «Командное владение решением» просит роли и зоны ответственности");
  }

  {
    const s = lightSlide(++n);
    title(s, "Коротко о проекте");
    text(s, "Жэка - один бот в MAX для любой УК. Житель сообщает о проблеме за минуту, видит статус и сам принимает работу. Раз в месяц передаёт показания. УК получает один канал вместо звонков и выполняет требование ПП РФ № 40 о работе с жителями через MAX", { x: 0.6, y: 1.55, w: 8.3, h: 1.6, fontSize: 17 });
    const cols = [
      ["LuUser", "Жителю", "Заявка с фото за минуту, статус и срок в сообщениях бота, приёмка работы с фото «было - стало»"],
      ["LuBuilding2", "УК", "Заявки, показания, объявления в домовые чаты, исполнители и аналитика в одном кабинете"],
      ["LuChartBar", "Рынку", "Обезличенный бенчмарк УК и счётчик спроса на дома, где УК ещё не подключена"],
    ];
    for (let i = 0; i < cols.length; i++) {
      const [ic, h, body] = cols[i];
      const x = 0.6 + i * 4.1;
      card(s, x, 3.55, 3.8, 3.2);
      await badge(s, ic, x + 0.3, 3.8, 0.75);
      text(s, h, { x: x + 0.3, y: 4.7, w: 3.2, h: 0.45, fontFace: H, bold: true, fontSize: 17 });
      text(s, body, { x: x + 0.3, y: 5.2, w: 3.25, h: 1.4, fontSize: 14 });
    }
    says(s, "Свой человек в ЖКХ: принял, передал, проследил", 8.9, 1.7, 2.45, 1.0, 1.1, { fontSize: 12.5 });
  }

  {
    const s = lightSlide(++n);
    title(s, "Потекло. А кому звонить?");
    text(s, [
      { text: "Собственник квартиры в доме под управлением УК", options: { bold: true } },
      { text: " при бытовой проблеме (протечка, лифт, мусор) хочет, чтобы её устранили. Но он не знает, кто отвечает: УК, ресурсник или город. Ищет телефон, дозванивается и не видит ни статуса, ни сроков" },
    ], { x: 0.6, y: 1.55, w: 7.4, h: 1.7, fontSize: 17 });
    s.addText("Проблема решается долго, доверие к УК падает", { shape: pres.shapes.ROUNDED_RECTANGLE, isTextBox: true, x: 0.6, y: 3.35, w: 7.2, h: 0.62, rectRadius: 0.31, fill: { color: C.vest }, line: { color: C.night, width: 1.5 }, fontFace: B, bold: true, fontSize: 16, color: C.night, align: "center", valign: "middle", margin: 0 });
    const pains = [
      ["LuCircleHelp", "Не знает, кому писать", "УК, РСО или муниципалитет"],
      ["LuPhoneCall", "Долго дозваниваться", "Диспетчерская занята, ответ устный"],
      ["LuEye", "Не видит статуса", "Выполнено - это слова диспетчера"],
    ];
    for (let i = 0; i < pains.length; i++) {
      const [ic, h, body] = pains[i];
      const y = 4.35 + i * 0.95;
      await badge(s, ic, 0.6, y, 0.7);
      text(s, h, { x: 1.5, y: y + 0.02, w: 6, h: 0.35, bold: true, fontSize: 16 });
      text(s, body, { x: 1.5, y: y + 0.37, w: 6, h: 0.3, fontSize: 13.5, color: C.muted });
    }
    card(s, 8.6, 1.55, 4.13, 3.35, { fill: C.refl, flat: true, noLine: true });
    text(s, "Чем подтверждаем", { x: 8.9, y: 1.75, w: 3.6, h: 0.4, fontFace: H, bold: true, fontSize: 14 });
    text(s, bullets([
      "Эксперт трека, Минстрой Псковской обл.: жители не знают, зарегистрировано ли обращение и когда его рассмотрят",
      "Там же: непонятно, кто отвечает и куда обращаться - УК, ТСЖ или муниципалитет",
      "[Выводы CustDev: N интервью, ключевые цитаты]",
    ]), { x: 8.9, y: 2.25, w: 3.6, h: 2.55, fontSize: 12.5 });
    says(s, "Сегодня статус заявки - это то, что сказали по телефону", 8.6, 5.35, 2.75, 1.0, 1.1, { fontSize: 12.5 });
    s.addNotes("Формула проблемы из материалов трека: пользователь, контекст, результат, барьер, последствие. Факты отделены от гипотез. CustDev вставить обязательно: критерий «Пользовательская ценность» просит подтверждение данными или интервью");
  }

  {
    const s = darkSlide(++n);
    title(s, "Почему сейчас", { color: C.pure });
    const nums = [
      ["01.09.2026", "УК обязаны взаимодействовать с жителями через MAX", "ПП РФ от 26.01.2026 № 40", C.vest],
      ["4,2 млрд м²", "общая площадь жилищного фонда России", "Росстат, 2024", C.pure],
      ["49 312", "управляющих организаций в реестре", "Реформа ЖКХ, 09.2026", C.pure],
    ];
    nums.forEach(([big, cap, src, color], i) => {
      const x = 0.6 + i * 4.15;
      text(s, big, { x, y: 2.0, w: 4.0, h: 1.2, fontFace: H, bold: true, fontSize: 34, color, valign: "bottom" });
      text(s, cap, { x, y: 3.4, w: 3.7, h: 1.0, fontSize: 17, color: C.pure });
      text(s, src, { x, y: 4.45, w: 3.7, h: 0.35, fontSize: 12, color: C.refl });
    });
    text(s, "Требование уже действует, а готового инструмента у большинства УК нет\nЖэка закрывает его за УК и даёт жителю прозрачный канал", { x: 0.6, y: 5.85, w: 10.5, h: 0.8, fontSize: 16, color: C.pure });
  }

  {
    const s = lightSlide(++n);
    title(s, "Что знаем и что предполагаем");
    const cols = [
      ["LuCircleCheck", "Знаем", [
        "На обращение УК отвечает не позднее 10 рабочих дней (ПП РФ № 416, п. 36)",
        "Эксперт трека: жители не знают, принято ли обращение и когда ответят; у УК 50+ домов и чатов без модераторов",
        "Госуслуги Дом недоступен арендатору (эксперт трека)",
      ]],
      ["LuLightbulb", "Предполагаем", [
        "Номер и срок сразу после подачи снижают повторные звонки в диспетчерскую",
        "Ежемесячные показания удерживают жителя между редкими заявками",
        "Житель подтверждает работу, если это одна кнопка в чате",
        "УК подключится, чтобы выполнить ПП № 40 без своей разработки",
      ]],
      ["LuCircleHelp", "Проверим после запуска", [
        "Доля жителей дома, которые уже в MAX",
        "Время реакции первой УК до подключения",
      ]],
    ];
    for (let i = 0; i < cols.length; i++) {
      const [ic, h, items] = cols[i];
      const x = 0.6 + i * 4.12;
      card(s, x, 1.6, 3.88, 5.2, i === 2 ? { fill: C.white, flat: true, lw: 1, line: C.refl } : {});
      await badge(s, ic, x + 0.28, 1.85, 0.7, i === 1 ? { fill: C.vest, color: C.night } : {});
      text(s, h, { x: x + 1.12, y: 1.95, w: 2.6, h: 0.5, fontFace: H, bold: true, fontSize: 15, valign: "middle" });
      text(s, bullets(items, { gap: 8 }), { x: x + 0.28, y: 2.8, w: 3.35, h: 3.9, fontSize: 12.5 });
    }
    s.addNotes("Организаторы просят разделять знаем, предполагаем и не знаем. Гипотезы проверяются метриками со слайда об эффекте после запуска");
  }

  {
    const s = lightSlide(++n);
    title(s, "Для кого");
    card(s, 0.6, 1.6, 6.1, 5.2);
    await badge(s, "LuHouse", 0.9, 1.9, 0.8, { fill: C.vest, color: C.night });
    text(s, "Приоритетный сегмент", { x: 1.9, y: 1.95, w: 4.5, h: 0.3, fontSize: 13, color: C.muted, bold: true });
    text(s, "Собственник квартиры в МКД под управлением УК", { x: 1.9, y: 2.25, w: 4.6, h: 0.9, fontFace: H, bold: true, fontSize: 16 });
    text(s, bullets([
      "Первым сталкивается с проблемой в квартире и в доме",
      "Платит по квитанции и хочет понимать, за что",
      "Раз в месяц передаёт показания: это превращает редкую заявку в привычку",
      "Голосует на собраниях и хочет знать, наберётся ли кворум",
    ], { gap: 8 }), { x: 0.9, y: 3.35, w: 5.5, h: 3.2, fontSize: 15 });
    const others = [
      ["LuUserCog", "Сотрудник УК", "Диспетчер и админ: заявки, дома, показания, объявления"],
      ["LuHardHat", "Исполнитель", "Мастер: карточка заявки прямо в диалоге с ботом, без мини-приложения"],
      ["LuVote", "Председатель совета дома", "Опросы, прогноз кворума, домовой чат"],
      ["LuKeyRound", "Арендатор", "Входит по коду собственника, без начислений и голосов"],
    ];
    for (let i = 0; i < others.length; i++) {
      const [ic, h, body] = others[i];
      const y = 1.6 + i * 1.33;
      card(s, 7.0, y, 5.73, 1.15, { fill: C.pure, flat: true, lw: 1, line: C.refl });
      await badge(s, ic, 7.2, y + 0.22, 0.7);
      text(s, h, { x: 8.1, y: y + 0.17, w: 4.4, h: 0.35, bold: true, fontSize: 15 });
      text(s, body, { x: 8.1, y: y + 0.52, w: 4.45, h: 0.55, fontSize: 12.5, color: C.muted });
    }
  }

  {
    const s = lightSlide(++n);
    title(s, "Было и стало");
    const rows = [
      ["Узнать, кто отвечает", "Искать в квитанции и на доске у подъезда", "Бот знает УК дома, дом можно найти по адресу, геопозиции или QR"],
      ["Сообщить о проблеме", "Дозвон в диспетчерскую, устно", "Заявка с фото и категорией за минуту"],
      ["Узнать статус", "Перезванивать", "Бот пишет при каждой смене статуса"],
      ["Подтвердить работу", "Диспетчер отмечает «выполнено»", "Житель принимает работу по фото и может подать повторную заявку"],
      ["Передать показания", "Бумажка в ящике или сайт УК", "Фото счётчика, распознанное значение, сравнение с домом"],
      ["Понять квитанцию", "Звонок диспетчеру, который не знает ответа", "Разбор суммы: объём или тариф, построчно"],
    ];
    const hdr = { bold: true, color: C.pure, fontFace: B, fontSize: 14, valign: "middle" };
    const tbl = [[
      { text: "Задача жителя", options: { ...hdr, fill: { color: C.navy } } },
      { text: "Сейчас", options: { ...hdr, fill: { color: C.navy } } },
      { text: "С Жэкой", options: { ...hdr, fill: { color: C.deep } } },
    ]];
    rows.forEach(([a, b, c], i) => {
      const fill = { color: i % 2 ? C.white : C.pure };
      tbl.push([
        { text: a, options: { bold: true, fill } },
        { text: b, options: { fill, color: C.muted } },
        { text: c, options: { fill } },
      ]);
    });
    s.addTable(tbl, { x: 0.6, y: 1.6, w: 12.13, colW: [3.0, 4.1, 5.03], fontFace: B, fontSize: 13.5, color: C.navy, border: { type: "solid", pt: 1, color: C.refl }, rowH: 0.7, margin: [4, 10, 4, 10], valign: "middle" });
  }

  {
    const s = lightSlide(++n);
    title(s, "Чем закрывают задачу сейчас");
    const cols = ["Телефон диспетчерской", "Домовой чат", "Сайт или приложение УК", "Госуслуги Дом", "Жэка"];
    const rows = [
      ["Видно, кто отвечает за дом", ["-", "±", "+", "+", "+"]],
      ["Статус и срок заявки видны", ["-", "-", "±", "±", "+"]],
      ["Работу подтверждает житель", ["-", "-", "-", "-", "+"]],
      ["Показания без визита и звонка", ["-", "-", "±", "+", "+"]],
      ["Один вход для любой УК", ["-", "-", "-", "+", "+"]],
      ["Доступно арендатору", ["+", "±", "±", "-", "+"]],
      ["Кабинет УК с исполнителями", ["-", "-", "±", "-", "+"]],
    ];
    const last = cols.length - 1;
    const hdr = { bold: true, color: C.pure, fontFace: B, fontSize: 12.5, align: "center", valign: "middle" };
    const tbl = [[{ text: "", options: { fill: { color: C.white } } }, ...cols.map((c, i) => ({ text: c, options: { ...hdr, fill: { color: i === last ? C.deep : C.navy } } }))]];
    rows.forEach(([label, marks], r) => {
      const fill = { color: r % 2 ? C.white : C.pure };
      tbl.push([
        { text: label, options: { bold: true, fill } },
        ...marks.map((m, i) => ({ text: m === "+" ? "да" : m === "-" ? "нет" : "частично", options: { fill, align: "center", bold: i === last, color: m === "+" ? (i === last ? C.deep : C.navy) : C.muted } })),
      ]);
    });
    s.addTable(tbl, { x: 0.6, y: 1.5, w: 12.13, colW: [3.33, 1.76, 1.76, 1.76, 1.76, 1.76], fontFace: B, fontSize: 13, color: C.navy, border: { type: "solid", pt: 1, color: C.refl }, rowH: 0.52, margin: [4, 8, 4, 8], valign: "middle" });
    text(s, "Госуслуги Дом - канал собственника в ГИС ЖКХ. Жэка закрывает то, чего там нет: арендатор, приёмка работы жителем, кабинет УК с исполнителями", { x: 0.6, y: 5.85, w: 12.1, h: 0.6, fontSize: 14, bold: true });
    text(s, "Арендатор и Госуслуги Дом: эксперт трека, вебинар хакатона. [Сверить оценки Госуслуги Дом и приложений УК с актуальными версиями]", { x: 0.6, y: 6.5, w: 11.5, h: 0.35, fontSize: 11.5, color: C.muted });
  }

  {
    const s = lightSlide(++n);
    title(s, "Основной сценарий жителя");
    const steps = [
      ["LuQrCode", "Открыл бота", "По QR у лифта, из домового чата или по ссылке"],
      ["LuMapPin", "Нашёл дом", "Город, улица, дом или геопозиция. Согласие на ПД до выбора дома"],
      ["LuCamera", "Оставил заявку", "Описание, категория, фото. В приложении категорию подсказывает модель"],
      ["LuBell", "Видит статус", "Номер, срок, сообщение при каждой смене статуса"],
      ["LuCircleCheck", "Принял работу", "Фото «было - стало», оценка или повторная заявка"],
    ];
    const cw = 2.25;
    const gap = (12.13 - cw * steps.length) / (steps.length - 1);
    for (let i = 0; i < steps.length; i++) {
      const [ic, h, body] = steps[i];
      const x = 0.6 + i * (cw + gap);
      card(s, x, 2.0, cw, 3.1);
      await badge(s, ic, x + 0.25, 2.25, 0.72, i === 2 ? { fill: C.vest, color: C.night } : {});
      text(s, `${i + 1}`, { x: x + cw - 0.65, y: 2.3, w: 0.4, h: 0.5, fontFace: H, bold: true, fontSize: 20, color: C.refl, align: "right" });
      text(s, h, { x: x + 0.25, y: 3.12, w: cw - 0.4, h: 0.4, bold: true, fontSize: 15.5 });
      text(s, body, { x: x + 0.25, y: 3.55, w: cw - 0.4, h: 1.45, fontSize: 12.5 });
      if (i < steps.length - 1) {
        s.addShape(pres.shapes.LINE, { x: x + cw + 0.04, y: 3.55, w: gap - 0.08, h: 0, line: { color: C.navy, width: 1.5, endArrowType: "triangle" } });
      }
    }
    says(s, "Заявка № 1542 «Протечка» принята в работу. Срок: до 18:40. Кнопка в сообщении откроет заявку", 1.97, 5.45, 5.7, 0.95, 1.1, { fontSize: 13, side: "left" });
    text(s, "Бот ведёт короткие диалоги, статусы и уведомления, мини-приложение отвечает за формы, списки и историю", { x: 8.1, y: 5.6, w: 4.6, h: 0.95, fontSize: 13, color: C.muted });
  }

  {
    const s = lightSlide(++n);
    title(s, "Две опоры продукта");
    card(s, 0.6, 1.65, 5.9, 5.15);
    await badge(s, "LuWrench", 0.9, 1.95, 0.75);
    text(s, "Заявки: редко, но больно", { x: 1.85, y: 2.08, w: 4.5, h: 0.5, fontFace: H, bold: true, fontSize: 16 });
    text(s, bullets([
      "Редкое, но самое болезненное событие",
      "Полный цикл: подача, работа, исполнитель, приёмка жителем, оценка",
      "Приводит жителя в бот, но удержать его одними заявками нельзя",
    ], { gap: 8 }), { x: 0.9, y: 2.95, w: 5.35, h: 1.55, fontSize: 14.5 });
    card(s, 0.9, 4.6, 5.3, 1.95, { fill: C.white, flat: true, lw: 1, line: C.refl, r: 0.14 });
    text(s, [
      { text: "№ 1542 «Протечка», срок до 18:40", options: { bold: true, fontSize: 16, color: C.navy, breakLine: true, paraSpaceAfter: 4 } },
      { text: "09:12  подана с фото, принята через 28 минут", options: { fontSize: 13, breakLine: true, paraSpaceAfter: 2 } },
      { text: "15:30  на приёмке, житель принял работу", options: { fontSize: 13, breakLine: true, paraSpaceAfter: 6 } },
      { text: "Ход заявки: каждый шаг - сообщение в MAX", options: { fontSize: 11.5, color: C.muted } },
    ], { x: 1.17, y: 4.75, w: 4.9, h: 1.7 });
    card(s, 6.83, 1.65, 5.9, 5.15);
    await badge(s, "LuGauge", 7.13, 1.95, 0.75, { fill: C.vest, color: C.night });
    text(s, "Счётчики: каждый месяц", { x: 8.08, y: 2.08, w: 4.5, h: 0.5, fontFace: H, bold: true, fontSize: 16 });
    text(s, bullets([
      "Фото, распознанное значение, подтверждение",
      "Расход и сравнение со средним по дому",
      "Напоминания в окно подачи и перед поверкой",
    ], { gap: 8 }), { x: 7.13, y: 2.95, w: 5.35, h: 1.55, fontSize: 14.5 });
    card(s, 7.13, 4.6, 5.3, 1.95, { fill: C.white, flat: true, lw: 1, line: C.refl, r: 0.14 });
    text(s, [
      { text: "+820 ₽ к августу", options: { bold: true, fontSize: 16, color: C.navy, breakLine: true, paraSpaceAfter: 4 } },
      { text: "+640  ГВС: расход вырос на 4 м³", options: { fontSize: 13, breakLine: true, paraSpaceAfter: 2 } },
      { text: "+180  содержание: новый тариф с 01.09", options: { fontSize: 13, breakLine: true, paraSpaceAfter: 6 } },
      { text: "Разбор квитанции: почему выросла сумма", options: { fontSize: 11.5, color: C.muted } },
    ], { x: 7.4, y: 4.75, w: 4.9, h: 1.7 });
  }

  {
    const s = lightSlide(++n);
    title(s, "Чего нет в обычном боте заявок");
    const feats = [
      ["LuCopy", "Склейка коллективных заявок", "«На это уже пожаловались 7 соседей»: одна группа на стояк вместо дюжины дублей"],
      ["LuHardHat", "Исполнитель и приёмка", "Мастер жмёт «выехал - готово» и присылает фото, «выполнено» подтверждает житель"],
      ["LuReceipt", "Разбор квитанции", "Рост суммы раскладывается на объём и тариф, спор уходит заявкой с расчётом"],
      ["LuScale", "Прогноз кворума по площади", "«47 квартир - 38% площади»: председатель видит, прошло бы собрание"],
      ["LuQrCode", "QR на подъезде", "Дом уже выбран, остаются согласие и номер квартиры"],
      ["LuPhone", "Заявка по звонку", "Звонок диспетчеру попадает в тот же прозрачный конвейер"],
    ];
    for (let i = 0; i < feats.length; i++) {
      const [ic, h, body] = feats[i];
      const col = i % 3;
      const row = Math.floor(i / 3);
      const x = 0.6 + col * 4.12;
      const y = 1.65 + row * 2.6;
      card(s, x, y, 3.88, 2.35);
      await badge(s, ic, x + 0.28, y + 0.28, 0.7);
      text(s, h, { x: x + 1.12, y: y + 0.3, w: 2.6, h: 0.7, bold: true, fontSize: 15, valign: "middle" });
      text(s, body, { x: x + 0.28, y: y + 1.15, w: 3.35, h: 1.1, fontSize: 13 });
    }
  }

  {
    const s = lightSlide(++n);
    title(s, "Как это выглядит");
    text(s, "Экраны мини-приложения на модельных данных", { x: 7.7, y: 0.8, w: 5.0, h: 0.35, fontSize: 13, color: C.muted, align: "right" });
    const shots = [
      ["01-home.png", "Главная: заявка на приёмке, окно показаний, опрос"],
      ["02-new-request.png", "Заявка: модель подсказала категорию, соседи уже сообщили"],
      ["03-request.png", "Статус, срок и ход заявки"],
      ["04-meters.png", "Показания: расход и сравнение с домом"],
    ];
    const h = 4.75;
    const w = (h - 0.2) * (780 / 1688) + 0.2;
    const gap = (12.13 - w * shots.length) / (shots.length - 1);
    shots.forEach(([file, caption], i) => {
      const x = 0.6 + i * (w + gap);
      phone(s, file, x, 1.5, h);
      text(s, caption, { x: x - 0.2, y: 6.38, w: w + 0.4, h: 0.55, fontSize: 12, align: "center" });
    });
    s.addNotes("Скриншоты мини-приложения на мок-данных фронтенда. Сообщения бота показываем вживую в демо");
  }

  {
    const s = lightSlide(++n);
    title(s, "Кабинет УК");
    const items = [
      ["LuWrench", "Заявки", "Сообщение о каждой новой заявке, группы коллективных заявок, назначение исполнителя, просроченные заявки"],
      ["LuCalendarClock", "Приём и доступ в квартиры", "Запись жителей на приём, сбор окон доступа: «ответили 9 из 14»"],
      ["LuMegaphone", "Дома и объявления", "Жители, подтверждение квартир, показания, объявления в домовые чаты, QR для подъездов"],
      ["LuChartBar", "Аналитика", "Время реакции, доля повторных, исполнители, каналы заявок, обезличенный бенчмарк с другими УК"],
    ];
    for (let i = 0; i < items.length; i++) {
      const [ic, h, body] = items[i];
      const y = 1.6 + i * 1.3;
      await badge(s, ic, 0.6, y, 0.72);
      text(s, h, { x: 1.55, y: y - 0.02, w: 5.3, h: 0.38, bold: true, fontSize: 16 });
      text(s, body, { x: 1.55, y: y + 0.38, w: 5.3, h: 0.8, fontSize: 13 });
    }
    const w = phone(s, "05-admin-requests.png", 7.45, 1.55, 5.0);
    phone(s, "06-analytics.png", 7.45 + w + 0.35, 1.55, 5.0);
  }

  {
    const s = lightSlide(++n);
    title(s, "Возможности MAX сверх минимума");
    const items = [
      ["LuMessageCircle", "Домовые чаты", "Бот в чате дома: привязка к дому, объявления УК, список закрепов"],
      ["LuBell", "Три уровня уведомлений", "Со звуком, без звука или выключены, по категориям. Статусы своих заявок не отключаются"],
      ["LuSparkles", "Живые сообщения", "Карточка исполнителя и приёмка редактируются на месте, а не множатся"],
      ["LuLink", "Диплинки и QR", "Приглашения сотрудников и арендаторов, подъездный QR, демо-доступ"],
      ["LuSmartphone", "Связка бот + мини-приложение", "Уведомление открывает нужную заявку в приложении, сотруднику - в кабинете УК"],
    ];
    for (let i = 0; i < items.length; i++) {
      const [ic, h, body] = items[i];
      const col = i < 3 ? 0 : 1;
      const row = i < 3 ? i : i - 3;
      const x = 0.6 + col * 6.2;
      const y = 1.65 + row * 1.6;
      card(s, x, y, 5.9, 1.35);
      await badge(s, ic, x + 0.25, y + 0.3, 0.72);
      text(s, h, { x: x + 1.2, y: y + 0.2, w: 4.5, h: 0.38, bold: true, fontSize: 15.5 });
      text(s, body, { x: x + 1.2, y: y + 0.58, w: 4.5, h: 0.7, fontSize: 12.5 });
    }
    says(s, "У настоящих мастеров уже стоит MAX", 7.45, 5.45, 3.9, 0.95, 1.1, { fontSize: 13 });
    s.addNotes("Кандидат на платформенный бонус +0,15: возможность должна работать от начала до конца и быть описана в материалах");
  }

  {
    const s = lightSlide(++n);
    title(s, "Ожидаемый эффект");
    text(s, "Если житель сообщает о проблеме в MAX и сам принимает работу, заявка регистрируется быстрее, а статус «выполнено» становится фактом, потому что его подтверждает вторая сторона", { x: 0.6, y: 1.5, w: 12, h: 0.9, fontSize: 15.5 });
    const big = [
      ["< 1 мин", "от проблемы до заявки с номером", "гипотеза, замерим после запуска: сейчас поиск телефона и дозвон"],
      ["72 ч", "самый длинный срок категории", "норматив ПП РФ № 416, п. 36: 10 рабочих дней"],
      ["1 группа", "вместо дюжины дублей со стояка", "склейка по дому, категории и окну"],
    ];
    big.forEach(([v, cap, sub], i) => {
      const x = 0.6 + i * 4.12;
      card(s, x, 2.6, 3.88, 2.1);
      text(s, v, { x: x + 0.3, y: 2.8, w: 3.4, h: 0.85, fontFace: H, bold: true, fontSize: 32, color: i === 0 ? C.vest : C.deep, valign: "middle" });
      text(s, cap, { x: x + 0.3, y: 3.65, w: 3.4, h: 0.4, bold: true, fontSize: 14 });
      text(s, sub, { x: x + 0.3, y: 4.05, w: 3.4, h: 0.5, fontSize: 12, color: C.muted });
    });
    text(s, "Как проверим после запуска", { x: 0.6, y: 5.0, w: 6, h: 0.4, fontFace: H, bold: true, fontSize: 14 });
    text(s, bullets([
      "Время реакции УК рядом со сроком категории",
      "Доля работ, принятых жителем, против закрытых по таймауту",
      "Доля повторных заявок",
    ]), { x: 0.6, y: 5.45, w: 6, h: 1.4, fontSize: 13.5 });
    text(s, bullets([
      "Доля заявок цифрой против записанных со звонка",
      "Доля показаний без визита и звонка",
      "Охват: доля квартир дома в продукте",
    ]), { x: 6.8, y: 5.45, w: 5.9, h: 1.4, fontSize: 13.5 });
    s.addNotes("Цифры эффекта - гипотезы до запуска, так и проговаривать. Все метрики уже собираются в событиях и видны на дашборде");
  }

  {
    const s = lightSlide(++n);
    title(s, "Границы MVP");
    const cols = [
      ["Must: сделано", C.deep, ["Согласие на ПД и онбординг в боте и приложении", "Заявки полным циклом с ролью УК и уведомлениями", "Счётчики: окно, проверка, поверка, расход", "Карточка дома, опросы, домовые чаты", "Роли в УК, приглашения, демо-доступ", "Аналитика УК, Docker, README"]],
      ["Should: сделано", C.blue, ["OCR показаний и подсказка категории", "Подтверждение квартиры, квитанции, демо-оплата", "Склейка заявок, QR, исполнитель и приёмка", "Приём и сбор доступа, разбор квитанции", "Прогноз кворума, заявка по звонку, бенчмарк"]],
      ["Won't: сознательно нет", C.navy, ["Реальная оплата и эквайринг", "Юридически значимое ОСС", "Интеграция с ГИС ЖКХ и биллингом", "Кабинет оператора платформы", "Своя копия сервиса у каждой УК"]],
    ];
    cols.forEach(([h, color, items], i) => {
      const x = 0.6 + i * 4.12;
      s.addText(h, { shape: pres.shapes.ROUNDED_RECTANGLE, isTextBox: true, x, y: 1.6, w: 3.88, h: 0.55, rectRadius: 0.27, fill: { color }, color: C.pure, fontFace: B, bold: true, fontSize: 14, align: "center", valign: "middle", margin: 0 });
      text(s, bullets(items, { gap: 8 }), { x: x + 0.1, y: 2.4, w: 3.7, h: 4.4, fontSize: 13.5 });
    });
  }

  {
    const s = lightSlide(++n);
    title(s, "Архитектура");
    const box = (label, sub, x, y, w, h, o = {}) => {
      card(s, x, y, w, h, { flat: !o.main, fill: o.fill || C.pure, lw: o.main ? 1.5 : 1, line: o.main ? C.night : C.navy, r: 0.12 });
      text(s, [
        { text: label, options: { bold: true, fontSize: 14, breakLine: !!sub, color: o.color || C.navy } },
        ...(sub ? [{ text: sub, options: { fontSize: 11, color: o.subColor || C.muted } }] : []),
      ], { x: x + 0.15, y, w: w - 0.3, h, align: "center", valign: "middle" });
    };
    const arrow = (x1, y1, x2, y2, o = {}) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipH: x2 < x1, flipV: y2 < y1, line: { color: C.navy, width: 1.25, endArrowType: "triangle", beginArrowType: o.both ? "triangle" : undefined, dashType: o.dash ? "dash" : "solid" } });

    box("MAX", "бот, мини-приложение, домовые чаты", 0.6, 3.05, 2.3, 1.1, { main: true, fill: C.deep, color: C.pure, subColor: C.refl });
    box("nginx", "за TLS хоста, разводит по путям", 3.5, 3.05, 1.9, 1.1);
    box("web", "React + TypeScript, max-ui", 6.0, 1.65, 2.5, 1.0);
    box("api", "FastAPI, вебхук бота maxo", 6.0, 3.1, 2.5, 1.0, { main: true });
    box("worker, scheduler", "taskiq: рассылки, напоминания", 6.0, 4.55, 2.5, 1.0);
    box("PostgreSQL 16", "дома, заявки, показания, события", 9.3, 2.35, 3.43, 1.0);
    box("Redis", "очередь задач", 9.3, 3.8, 3.43, 0.8);
    box("Yandex Vision OCR, AI Studio", "показания по фото, категория заявки; необязательны", 9.3, 5.05, 3.43, 1.05);

    arrow(2.9, 3.6, 3.5, 3.6, { both: true });
    arrow(5.4, 3.35, 6.0, 2.15);
    arrow(5.4, 3.6, 6.0, 3.6);
    arrow(8.5, 3.45, 9.3, 2.85);
    arrow(8.5, 3.75, 9.3, 4.2);
    arrow(7.25, 4.1, 7.25, 4.55);
    arrow(8.5, 5.05, 9.3, 4.35);
    arrow(8.5, 3.9, 9.3, 5.45, { dash: true });
    arrow(6.0, 5.05, 2.9, 3.95, { dash: true });

    text(s, "Один бот на все УК: мультитенант на общей схеме, изоляция фильтром по организации. Docker Compose поднимает всё одной командой", { x: 0.6, y: 6.35, w: 11.5, h: 0.6, fontSize: 13.5 });
    s.addNotes("Сообщения уходят после коммита транзакции; вебхук отвечает за 30 секунд, тяжёлое уходит в taskiq. initData проверяется HMAC на токене бота");
  }

  {
    const s = lightSlide(++n);
    title(s, "Данные и интеграции");
    const big = [["165", "реальных домов в справочнике"], ["3", "города: Москва, Санкт-Петербург, Казань"], ["34", "реальные УК из карточек домов"]];
    big.forEach(([v, cap], i) => {
      const x = 0.6 + i * 2.2;
      text(s, v, { x, y: 1.55, w: 2.0, h: 0.8, fontFace: H, bold: true, fontSize: 34, color: C.deep, valign: "bottom" });
      text(s, cap, { x, y: 2.4, w: 1.95, h: 0.8, fontSize: 12.5 });
    });
    card(s, 0.6, 3.5, 6.2, 3.3, { flat: true, lw: 1, line: C.refl });
    text(s, "Открытые данные", { x: 0.9, y: 3.7, w: 5.6, h: 0.4, fontFace: H, bold: true, fontSize: 14 });
    text(s, bullets([
      "Реформа ЖКХ: дома (год, этажность, площадь, помещения) и реестр УО, выгрузка на сентябрь 2026",
      "OpenStreetMap: координаты через Nominatim и Overpass",
      "ГИС ЖКХ: справочники НСИ для видов счётчиков и услуг",
    ], { gap: 7 }), { x: 0.9, y: 4.2, w: 5.7, h: 2.5, fontSize: 13 });
    card(s, 7.1, 1.55, 5.63, 5.25, { flat: true, lw: 1, line: C.refl });
    text(s, "Модельные данные", { x: 7.4, y: 1.75, w: 5, h: 0.4, fontFace: H, bold: true, fontSize: 14 });
    text(s, bullets([
      "Начисления, квитанции, лицевые счета, показания: синтетика, помечена в интерфейсе",
      "Пять демо-УК с заведомо неверными ИНН и историей за 6 месяцев",
      "Лицевой счёт у всех квартир - её номер с нулями до 10 цифр, например 0000000012",
      "Оплата демонстрационная, деньги не списываются",
    ], { gap: 7 }), { x: 7.4, y: 2.25, w: 5.1, h: 2.2, fontSize: 13 });
    text(s, "Для продакшена", { x: 7.4, y: 4.55, w: 5, h: 0.4, fontFace: H, bold: true, fontSize: 14 });
    text(s, bullets([
      "Выгрузка биллинга УК в таблицу начислений",
      "ГИС ЖКХ API для домов и лицевых счетов",
      "ЕСИА или письмо на домен УК для проверки организации",
    ], { gap: 7 }), { x: 7.4, y: 5.0, w: 5.1, h: 1.7, fontSize: 13 });
  }

  {
    const s = lightSlide(++n);
    title(s, "Правовой контур");
    const items = [
      ["LuFileText", "ПП РФ № 40", "Жэка - канал, через который УК работает с жителями в MAX: обращения и запись на приём"],
      ["LuClock", "ПП РФ № 416", "п. 35: ответ тем же каналом. п. 36: сроки всех категорий короче норматива в 10 рабочих дней. п. 38: заявки хранятся 3 года"],
      ["LuShieldCheck", "152-ФЗ", "Согласие до выбора дома, версия и дата согласия в базе. Данные жителя видит только УК его дома"],
      ["LuVote", "Опросы - не ОСС", "Опрос помечен как предварительный: это репетиция собрания с прогнозом кворума, а не юридическое решение"],
    ];
    for (let i = 0; i < items.length; i++) {
      const [ic, h, body] = items[i];
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = 0.6 + col * 6.2;
      const y = 1.65 + row * 2.6;
      card(s, x, y, 5.9, 2.3);
      await badge(s, ic, x + 0.28, y + 0.28, 0.72);
      text(s, h, { x: x + 1.2, y: y + 0.4, w: 4.4, h: 0.45, fontFace: H, bold: true, fontSize: 15 });
      text(s, body, { x: x + 0.28, y: y + 1.15, w: 5.35, h: 1.05, fontSize: 13 });
    }
  }

  {
    const s = lightSlide(++n);
    title(s, "Что сохраняется, что адаптируется");
    card(s, 0.6, 1.6, 5.9, 4.3);
    text(s, "Ядро: переносится без изменений", { x: 0.9, y: 1.85, w: 5.4, h: 0.45, fontFace: H, bold: true, fontSize: 15 });
    text(s, bullets([
      "Проблема жителя и сценарий заявки с приёмкой",
      "Один бот на все УК, модель данных дом - квартира - житель",
      "Счётчики, опросы, домовые чаты, роли в УК",
      "Интерфейс бота и мини-приложения",
    ], { gap: 9 }), { x: 0.9, y: 2.5, w: 5.35, h: 3.2, fontSize: 14.5 });
    card(s, 6.83, 1.6, 5.9, 4.3, { fill: C.white, flat: true, lw: 1, line: C.refl });
    text(s, "Переменная часть: меняется под регион и УК", { x: 7.13, y: 1.85, w: 5.4, h: 0.75, fontFace: H, bold: true, fontSize: 15 });
    text(s, bullets([
      "Справочник домов: выгрузка Реформы ЖКХ по региону",
      "Тарифы, окна подачи показаний, часовой пояс дома",
      "Категории и сроки заявок под регламент УК",
      "Интеграции: биллинг УК, ГИС ЖКХ, региональные системы",
      "Бренд: white-label бот на токене УК на том же ядре",
    ], { gap: 7 }), { x: 7.13, y: 2.65, w: 5.35, h: 3.1, fontSize: 14 });
    card(s, 0.6, 6.1, 12.13, 0.75, { fill: C.refl, flat: true, noLine: true, r: 0.12 });
    text(s, [
      { text: "Новый регион без изменений ядра: ", options: { bold: true } },
      { text: "скрипт загружает выгрузку КР 1.1 и реестр УО Реформы ЖКХ, под регион настраиваются выгрузка и разбор адресов. УК подключается сама по ИНН и коду регистрации, сотрудников зовёт ссылками, своих ИТ-специалистов не нужно" },
    ], { x: 0.85, y: 6.15, w: 11.7, h: 0.65, fontSize: 12.5, valign: "middle" });
  }

  {
    const s = lightSlide(++n);
    title(s, "Путь тиражирования");
    const stages = [
      ["Пилот", "1 УК, 5-10 домов", "QR в подъездах, пост в домовом чате, сотрудники по приглашениям"],
      ["Город", "все УК города", "Регистрация УК по ИНН, дома из реестра. Спрос жителей на неподключённые дома как аргумент для УК"],
      ["Регион", "Москва, СПб, Татарстан", "Скрипт выгрузки уже работает с КР 1.1 этих регионов, в демо 165 домов. Интеграция с биллингом крупных УК"],
      ["Сети и ТСЖ", "white-label", "Свой бот на токене УК на общем ядре. ТСЖ и ЖСК с той же механикой"],
    ];
    const cw = 2.85;
    const gap = (12.13 - cw * 4) / 3;
    stages.forEach(([h, sub, body], i) => {
      const x = 0.6 + i * (cw + gap);
      const top = 4.1 - i * 0.62;
      card(s, x, top, cw, 6.8 - top, i === 0 ? { fill: C.pure } : { fill: C.pure });
      text(s, `${i + 1}`, { x: x + 0.25, y: top + 0.2, w: 0.6, h: 0.5, fontFace: H, bold: true, fontSize: 22, color: i === 0 ? C.vest : C.deep });
      text(s, h, { x: x + 0.25, y: top + 0.75, w: cw - 0.5, h: 0.4, fontFace: H, bold: true, fontSize: 15 });
      text(s, sub, { x: x + 0.25, y: top + 1.15, w: cw - 0.5, h: 0.35, bold: true, fontSize: 12.5, color: C.deep });
      text(s, body, { x: x + 0.25, y: top + 1.55, w: cw - 0.45, h: 6.6 - top - 1.6, fontSize: 12.5 });
    });
    text(s, [
      { text: "Рынок: ", options: { bold: true } },
      { text: "TAM - 49 312 УО в реестре РФ. SAM - 59 853 МКД в Москве, Санкт-Петербурге и Казани. SOM - [оценка на 1-2 года]" },
    ], { x: 0.6, y: 1.6, w: 7.2, h: 1.0, fontSize: 13.5 });
    s.addNotes("Масштабирование весит больше всех продуктовых критериев (35%). Числа МКД: выгрузка КР 1.1 Реформы ЖКХ от 01.09.2026: Москва 30 292, СПб 23 674, Казань 5 887");
  }

  {
    const s = lightSlide(++n);
    title(s, "План пилота и внедрения");
    const q = [
      ["LuMapPin", "Где", "Одна УК и 5-10 её домов"],
      ["LuHandshake", "Как встраивается", "Диспетчер работает в кабинете вместо тетради. Звонки заводит заявкой, мастер получает карточку в MAX"],
      ["LuUsers", "Кто нужен", "Владелец процесса в УК, диспетчер, 2-3 мастера, председатель совета дома"],
      ["LuQrCode", "Как придут жители", "QR у лифта, объявление в домовом чате, строка в квитанции"],
    ];
    for (let i = 0; i < q.length; i++) {
      const [ic, h, body] = q[i];
      const y = 1.6 + i * 1.3;
      await badge(s, ic, 0.6, y, 0.72);
      text(s, h, { x: 1.55, y, w: 5.2, h: 0.38, bold: true, fontSize: 15.5 });
      text(s, body, { x: 1.55, y: y + 0.4, w: 5.2, h: 0.8, fontSize: 13 });
    }
    card(s, 7.2, 1.6, 5.53, 5.2);
    text(s, "Что замерим за 2 месяца", { x: 7.5, y: 1.85, w: 5, h: 0.45, fontFace: H, bold: true, fontSize: 15 });
    text(s, bullets([
      "Охват: доля подключенных квартир",
      "Доля заявок цифрой",
      "Время реакции УК в пределах норматива",
      "Доля работ, принятых жителем",
      "Доля показаний через бота",
    ], { gap: 9 }), { x: 7.5, y: 2.45, w: 5, h: 2.9, fontSize: 14.5 });
    text(s, "Следующий шаг: все дома первой УК, затем соседние УК города", { x: 7.5, y: 5.55, w: 5, h: 0.9, fontSize: 13.5, bold: true, color: C.deep });
  }

  {
    const s = lightSlide(++n);
    title(s, "Ограничения, риски и допущения");
    const cols = [
      ["LuTriangleAlert", "Ограничения MVP", ["Начисления и лицевые счета модельные", "Организация регистрируется без проверки", "Нет интеграции с ГИС ЖКХ и биллингом", "Опрос не заменяет ОСС"]],
      ["LuSmartphone", "Ограничения MAX", ["30 запросов в секунду на бота: рассылка на 1 000 жителей около 35 секунд", "Бот не пишет первым, пока житель его не открыл: звонок заводит диспетчер", "Бот помнит около 1 000 чатов: привязки чатов храним у себя"]],
      ["LuShieldCheck", "Риски и ответы", ["УК не хочет прозрачности: бенчмарк и спрос жителей", "Пересечение с Госуслуги Дом: делаем то, чего там нет", "Загрузка домов: публичный Nominatim - 1 запрос в секунду, Москва грузится около 18 часов. На масштабе свой Nominatim или DaData", "Ошибки OCR: житель подтверждает значение", "Персональные данные: согласие, доступ только своей УК"]],
    ];
    for (let i = 0; i < cols.length; i++) {
      const [ic, h, items] = cols[i];
      const x = 0.6 + i * 4.12;
      card(s, x, 1.6, 3.88, 5.2);
      await badge(s, ic, x + 0.28, 1.85, 0.7, i === 0 ? { fill: C.vest, color: C.night } : {});
      text(s, h, { x: x + 1.12, y: 1.95, w: 2.6, h: 0.5, fontFace: H, bold: true, fontSize: 14, valign: "middle" });
      text(s, bullets(items, { gap: 9 }), { x: x + 0.28, y: 2.85, w: 3.35, h: 3.8, fontSize: 13 });
    }
  }

  {
    const s = lightSlide(++n);
    title(s, "Источники");
    text(s, bullets([
      "ПП РФ от 26.01.2026 № 40; Минстрой России, 2026: взаимодействие УК с жителями через MAX",
      "ПП РФ от 15.05.2013 № 416 в ред. от 20.06.2026: правила управления МКД, пп. 34-38",
      "Приказ Минстроя об информационном взаимодействии через ГИС ЖКХ и MAX (publication.pravo.gov.ru)",
      "Росстат: жилищный фонд РФ, 2024",
      "Реформа ЖКХ (reformagkh.ru): отчёт КР 1.1 и реестр УО, выгрузка 01.09.2026",
      "ГИС ЖКХ (dom.gosuslugi.ru): справочники НСИ",
      "© участники OpenStreetMap, ODbL: координаты домов",
      "Документация MAX для разработчиков: dev.max.ru/docs",
      "Вебинары хакатона MAX, эксперт трека «Умный город» (Минстрой Псковской области): боли жителей и УК, Госуслуги Дом",
    ], { gap: 8 }), { x: 0.6, y: 1.6, w: 12.1, h: 4.3, fontSize: 14 });
    text(s, "Где использовался ИИ: ИИ-ассистент был вспомогательным инструментом и писал код по планам и правилам команды; продуктовые решения, архитектура и проверка - за командой. В продукте ИИ подсказывает категорию заявки и распознаёт показания", { x: 0.6, y: 6.1, w: 12.1, h: 0.6, fontSize: 13, color: C.muted });
  }

  {
    const s = darkSlide(++n);
    avatar(s, 8.0, 1.45, 4.6);
    avatar(s, 0.7, 0.7, 1.1);
    text(s, "Жэка", { x: 2.0, y: 0.72, w: 4, h: 0.62, fontFace: H, bold: true, fontSize: 32, color: C.pure, valign: "middle" });
    text(s, "Коммуналкин", { x: 2.0, y: 1.33, w: 4, h: 0.4, bold: true, fontSize: 18, color: C.pure, valign: "middle" });
    text(s, "Спасибо!", { x: 0.7, y: 2.7, w: 6, h: 1.2, fontFace: H, bold: true, fontSize: 48, color: C.pure, valign: "middle" });
    text(s, "Потекло, погасло, сломалось?\nПишите Жэке", { x: 0.7, y: 4.0, w: 6.2, h: 0.9, fontSize: 20, bold: true, color: C.pure });
    text(s, [
      { text: "max.ru/t260_hakaton_max_bot", options: { bold: true, breakLine: true } },
      { text: "github.com/K1rL3s/vkmax-mobilization", options: { breakLine: true } },
      { text: "Команда «Мобилизация»" },
    ], { x: 0.7, y: 5.4, w: 6.2, h: 1.1, fontSize: 14, color: C.pure });
    link(s, BOT, 0.7, 5.4, 3.0, 0.28);
    link(s, "https://github.com/K1rL3s/vkmax-mobilization", 0.7, 5.68, 3.6, 0.28);
  }

  fs.writeFileSync(OUT, await aimBubbles(await pres.write({ outputType: "nodebuffer" })));
  console.log(OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
