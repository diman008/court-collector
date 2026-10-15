"""Synthetic PDF carries verifiable physical page numbers."""
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
from judicial_intelligence.ingestion import extract_file


def make_page(writer, text):
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    fontref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"):fontref})
    })
    stream = DecodedStreamObject()
    stream.set_data(("BT /F1 12 Tf 50 250 Td (" + text + ") Tj ET").encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def test_two_pdf_pages_have_page_index_and_exact_text():
    writer = PdfWriter()
    make_page(writer, "FIRST COURT DOCUMENT")
    make_page(writer, "SECOND COURT DOCUMENT")
    output = BytesIO()
    writer.write(output)
    extracted = extract_file("record.pdf", output.getvalue())
    assert extracted.pagination_verified
    assert [(p.index,p.location_kind) for p in extracted.segments] == [
        (1,"physical_page"),(2,"physical_page")
    ]
    assert "FIRST COURT DOCUMENT" in extracted.segments[0].text
    assert "SECOND COURT DOCUMENT" in extracted.segments[1].text
