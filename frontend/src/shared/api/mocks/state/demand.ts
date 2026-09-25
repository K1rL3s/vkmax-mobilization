// спрос на подключение дома: жители непривязанного дома нажимают «хочу сюда
// сервис», УК видит число. К заявкам отношения не имеет, поэтому предмет свой
const state = {
  demand: new Map<number, number>([[4, 11]]),
  demandSent: new Set<number>(),
};

export const resetDemand = (): void => {
  state.demand = new Map([[4, 11]]);
  state.demandSent = new Set();
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

// дом, по которому спрос уже отправлен в УК: карточка дома показывает это
// подписью, а второй раз отправить нельзя
export const demandSent = (houseId: number): boolean =>
  state.demandSent.has(houseId);

export const demandTotal = (houseId: number): number =>
  state.demand.get(houseId) ?? 0;
