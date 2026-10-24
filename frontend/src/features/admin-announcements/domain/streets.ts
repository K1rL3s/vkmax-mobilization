type House = { city: string; street: string };

export const groupHousesByStreet = <T extends House>(houses: T[]) => {
  const groups: { street: string; houses: T[] }[] = [];

  for (const house of houses) {
    const street = `${house.city}, ${house.street}`;
    const group = groups.find((item) => item.street === street);

    if (group) {
      group.houses.push(house);
    } else {
      groups.push({ street, houses: [house] });
    }
  }

  return groups;
};
