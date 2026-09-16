import { useState } from "react";
import {
  Button,
  CellSimple,
  IconButton,
  Input,
  Typography,
} from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";

import {
  geoPinIcon,
  houseOutlineIcon,
  searchOutlineIcon,
} from "@/shared/assets/icons";
import { Routes } from "@/shared/model/routes";
import { Icon } from "@/shared/ui/icon";

import {
  formatHouseAddress,
  searchHouses,
  type House,
} from "../model/houses.mock";

import styles from "./house-select.module.css";

const HighlightedStreet = ({
  house,
  query,
}: {
  house: House;
  query: string;
}) => {
  const index = house.street.toLowerCase().indexOf(query.trim().toLowerCase());
  const length = query.trim().length;

  if (index === -1) {
    return <>{formatHouseAddress(house)}</>;
  }

  return (
    <>
      ул. {house.street.slice(0, index)}
      <span className={styles.Match}>
        {house.street.slice(index, index + length)}
      </span>
      {house.street.slice(index + length)}, {house.number}
    </>
  );
};

const HouseSelectPage = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedHouse, setSelectedHouse] = useState<House | null>(null);
  const [apartment, setApartment] = useState("");

  const suggestions = selectedHouse ? [] : searchHouses(query);
  const showSuggestions = !selectedHouse && query.trim().length > 0;

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setSelectedHouse(null);
  };

  const handleSelect = (house: House) => {
    setSelectedHouse(house);
    setQuery(formatHouseAddress(house));
  };

  return (
    <div className={styles.Page}>
      <div className={styles.Form}>
        <div className={styles.Autocomplete}>
          <div className={styles.SearchRow}>
            <div className={styles.SearchInput}>
              <Input
                placeholder="Улица и номер дома"
                iconBefore={
                  <Icon
                    src={searchOutlineIcon}
                    size={20}
                    className={styles.SearchIcon}
                  />
                }
                value={query}
                onChange={(event) => handleQueryChange(event.target.value)}
              />
            </div>
            {/* TODO: определение дома по геолокации, когда появится API */}
            <IconButton
              variant="secondary"
              size="medium"
              aria-label="Определить по геолокации"
              disabled
            >
              <Icon src={geoPinIcon} size={20} className={styles.GeoIcon} />
            </IconButton>
          </div>

          {showSuggestions && (
            <div className={styles.Suggestions}>
              {suggestions.length > 0 ? (
                suggestions.map((house) => (
                  <CellSimple
                    key={house.id}
                    before={
                      <Icon
                        src={houseOutlineIcon}
                        className={styles.SuggestionIcon}
                      />
                    }
                    title={<HighlightedStreet house={house} query={query} />}
                    subtitle={house.city}
                    onClick={() => handleSelect(house)}
                  />
                ))
              ) : (
                <div className={styles.Empty}>
                  <Typography.Text variant="body-strong" color="primary">
                    Ничего не нашли
                  </Typography.Text>
                  <Typography.Text variant="description" color="secondary">
                    Проверьте название улицы или попробуйте ввести только её
                    часть
                  </Typography.Text>
                </div>
              )}
            </div>
          )}
        </div>

        <Input
          placeholder="Номер квартиры"
          inputMode="numeric"
          withClearButton={false}
          value={apartment}
          onChange={(event) => setApartment(event.target.value)}
        />
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          disabled={!selectedHouse || !apartment.trim()}
          onClick={() => navigate(Routes.HOME)}
        >
          Далее
        </Button>
      </div>
    </div>
  );
};

export const Component = HouseSelectPage;
