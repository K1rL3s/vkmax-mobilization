# AGENTS.md - Жэка Коммуналкин

A MAX mini-app and bot through which residents of apartment buildings talk to their management company. This file holds what backend and frontend share; their own rules live in `backend/AGENTS.md` and `frontend/AGENTS.md`. `CLAUDE.md` is a symlink to this file

## Domain terms

Russian product words, used the same way in code, copy and docs

- УК (`Organization`): a management company; serves houses and works with residents through the кабинет УК. Not «организация» in copy
- Подключенный дом (`is_connected`): its УК is registered (`org_id` set, `registered_at` not null), so requests reach people. Not «активный дом»
- Публичная карточка дома (`HouseCard`): what any resident sees about any house: passport, УК contacts, УК public stats. Never requests, announcements or anything about other residents
- Кабинет УК: the staff part of the mini-app, roles creator, admin and employee; an executor works only through the bot. Not «админка»
- Демо-УК: a fictional УК with seeded history. An enterable one has a shared cabinet behind a demo link; a background one shows only on maps and in the УК comparison. Not «демо-админка»
- Справочник домов: houses preloaded from the open registry, with a passport
- Дом, добавленный жителем (`added_by_resident`): created from an address a resident picked on the map; no passport
- Срочное объявление (`urgent` announcement): a fresh one highlights the house on the УК map (`urgent` filter and fields there). Not «отключение»
- Отключение (`HouseCard.outages`, `core/outages.py`): a utility supply break reported by the resource company; demo data for now. Not a УК announcement
- Личная / общая заявка (`Request.place`, enum `RequestPlace`: `flat` / `house`): the problem is in the author's flat or in the building (entrance, yard, common property). `CATEGORY_PLACES` fixes it for lift, garbage, entrance, yard (общая) and meter_error, charge_dispute (личная); for leak, heating, water_supply, electricity and other the author chooses, nothing preselected. Place never changes grouping
