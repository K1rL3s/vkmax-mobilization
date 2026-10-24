import itertools

import segno
from fpdf.enums import XPos, YPos

from zheka.infra.pdf.document import FAMILY, NOTE_GREY, PdfDocument

QR_SIZE = 130


class NeighbourLeaflet(PdfDocument):
    def __init__(
        self,
        address: str,
        link: str,
        *,
        connected: bool,
        demo: bool,
    ) -> None:
        super().__init__(
            "Наш дом в MAX",
            "Жэка Коммуналкин - бот и мини-приложение в MAX",
            demo=demo,
        )
        self._line("Наш дом в MAX", size=34, bold=True)
        self._line(address, size=16)
        self.ln(8)
        self._qr(link)
        self.ln(8)
        self._line("Наведите камеру и откройте в MAX", size=16, bold=True)
        self.ln(4)
        lines = (
            (
                "Заявки в УК с фото и сроком по закону",
                "Объявления и отключения по дому",
                "Показания счетчиков и опросы жильцов",
            )
            if connected
            else (
                "Карточка дома: УК, тарифы, капремонт",
                "Позовите УК в Жэку - она увидит, сколько соседей ждут",
                "Когда УК подключится, заявки и объявления будут здесь же",
            )
        )
        for line in lines:
            self._line(f"• {line}", size=14)

    def footer(self) -> None:
        self.set_y(-18)
        with self.local_context(text_color=NOTE_GREY):
            self.set_font(FAMILY, size=8)
            self.cell(0, 4, self._note, align="C")

    def _line(self, text: str, *, size: float, bold: bool = False) -> None:
        self.set_font(FAMILY, style="B" if bold else "", size=size)
        self.multi_cell(
            0,
            size * 0.5,
            text,
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.ln(2)

    def _qr(self, link: str) -> None:
        qr = segno.make_qr(link, error="m")
        modules, _ = qr.symbol_size(border=0)
        cell = QR_SIZE / modules
        left = (self.w - QR_SIZE) / 2
        top = self.get_y()
        self.set_fill_color(0)
        for row_index, row in enumerate(qr.matrix_iter(border=0)):
            column = 0
            for dark, run in itertools.groupby(row):
                width = len(list(run))
                if dark:
                    self.rect(
                        left + column * cell,
                        top + row_index * cell,
                        width * cell + 0.05,
                        cell + 0.05,
                        style="F",
                    )
                column += width
        self.set_y(top + QR_SIZE)
