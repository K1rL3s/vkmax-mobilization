// ограничения формы опроса - бизнес-правило, а не деталь вёрстки: их знают и
// схема проверки, и поля на экране
export const pollFormConstraints = {
  title: 120,
  option: 80,
  description: 500,
  optionsMin: 2,
  optionsMax: 6,
};
