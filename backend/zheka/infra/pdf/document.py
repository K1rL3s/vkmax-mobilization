from collections.abc import Sequence
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS = Path(__file__).with_name("fonts")
FAMILY = "DejaVu"
BODY_SIZE = 10
NOTE_GREY = 110
WATERMARK_GREY = 228


class PdfDocument(FPDF):
    def __init__(self, title: str, note: str, *, demo: bool) -> None:
        super().__init__(format="A4")
        self._note = note
        self._demo = demo
        self.set_margins(20, 18, 20)
        self.set_auto_page_break(auto=True, margin=26)
        self.add_font(FAMILY, fname=FONTS / "DejaVuSans.ttf")
        self.add_font(FAMILY, style="B", fname=FONTS / "DejaVuSans-Bold.ttf")
        self.set_title(title)
        self.set_creator("Жэка Коммуналкин")
        self.add_page()

    def header(self) -> None:
        if not self._demo:
            return
        with (
            self.local_context(text_color=WATERMARK_GREY),
            self.rotation(45, self.w / 2, self.h / 2),
        ):
            self.set_font(FAMILY, style="B", size=110)
            label = "ДЕМО"
            self.text(
                (self.w - self.get_string_width(label)) / 2,
                self.h / 2 + 15,
                label,
            )

    def footer(self) -> None:
        self.set_y(-22)
        with self.local_context(text_color=NOTE_GREY):
            self.set_font(FAMILY, size=7.5)
            self.multi_cell(
                0,
                3.6,
                f"{self._note}. Страница {self.page_no()} из {{nb}}",
                align="L",
            )

    def heading(self, text: str) -> None:
        self.set_font(FAMILY, style="B", size=12)
        self.multi_cell(0, 6, text, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def paragraph(
        self,
        text: str,
        *,
        size: float = BODY_SIZE,
        bold: bool = False,
        align: str = "J",
    ) -> None:
        self.set_font(FAMILY, style="B" if bold else "", size=size)
        self.multi_cell(
            0,
            size * 0.5,
            text,
            align=align,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.ln(1.5)

    def grid(
        self,
        headings: Sequence[str],
        rows: Sequence[Sequence[str]],
        widths: Sequence[float],
        *,
        line_height: float = 4.6,
    ) -> None:
        self.set_font(FAMILY, size=8.5)
        with self.table(
            col_widths=tuple(widths),
            text_align="LEFT",
            line_height=line_height,
            first_row_as_headings=True,
        ) as table:
            table.row(tuple(headings))
            for row in rows:
                table.row(tuple(row))
        self.ln(4)

    def render(self) -> bytes:
        return bytes(self.output())
