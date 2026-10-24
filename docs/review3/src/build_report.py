#!/usr/bin/env python3
"""Builds docs/review3/PYTHIA_Final_Report.docx and .pdf (Word does the PDF export and updates the table of contents).
Run: python build_report.py [--no-pdf]"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import demo_info  # noqa: E402
import rc1, rc1b, rc2b, rc3, rc3b, rc4  # noqa: E402
import report_data, report_tables, report_texts  # noqa: E402
from docbuilder import Report  # noqa: E402

OUT = HERE.parent
DOCX = OUT / "PYTHIA_Final_Report.docx"
PDF = OUT / "PYTHIA_Final_Report.pdf"


def compose(d, F):
    rc1.cover(d, F)
    d.p("**Contents**", size=13, after=4)
    d.toc("1-1")
    d.pagebreak()
    rc1.abstract(d, F)
    rc1b.sec2(d, F)
    rc1b.sec3(d, F)
    rc1b.sec4(d, F)
    rc1b.sec5(d, F)
    rc2b.sec6(d, F)
    rc2b.sec7(d, F)
    rc2b.sec8(d, F)
    rc2b.sec9(d, F)
    rc3b.sec10(d, F)
    rc3b.sec11(d, F)
    rc3b.sec12(d, F)
    rc3b.sec13(d, F)
    rc3.sec14(d, F)
    rc4.appendices(d, F)


def main():
    F = report_data.load()
    F = report_tables.extend(F)
    D = demo_info.build(F)
    F = report_texts.texts(F, D)
    hdr = "PYTHIA Final Report · BCSE307L Compiler Design · Team 2 · A15 · Review 3"
    d1 = Report(hdr)
    compose(d1, F)                       # pass 1: collect figure and table numbers
    d = Report(hdr, refs=d1.new_refs)
    compose(d, F)
    missing = [k for k, v in d.refs.items() if v is None]
    d.save(DOCX)
    print("saved", DOCX)
    if "--no-pdf" in sys.argv:
        return
    import win32com.client  # type: ignore
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(DOCX))
        doc.Fields.Update()
        doc.Save()
        doc.ExportAsFixedFormat(str(PDF), 17, False, 0)       # wdExportFormatPDF = 17
        pages = doc.ComputeStatistics(2)
        doc.Close(False)
    finally:
        word.Quit()
    print("pdf pages:", pages, PDF)


if __name__ == "__main__":
    main()
