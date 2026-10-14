''' Reading .xlsx and .xls uploads '''
import unittest
from io import BytesIO

import xlsxwriter
import xlwt
from openpyxl import Workbook

from be.ldapadmin.import_export import read_excel_rows, read_excel_sheets

SHEET = [
    ['id', 'name', 'count'],
    ['  a ', 'K\xf8benhavn', 3],
    ['b', '', 7],
]


def build_xlsx(sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for rows in sheets:
        ws = wb.create_sheet()
        for row in rows:
            ws.append(row)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def build_xlsx_writer(sheets):
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {'in_memory': True})
    for rows in sheets:
        ws = wb.add_worksheet()
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                ws.write(r, c, value)
    wb.close()
    return out.getvalue()


def build_xls(sheets):
    wb = xlwt.Workbook()
    for number, rows in enumerate(sheets):
        ws = wb.add_sheet('Sheet %d' % number)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                ws.write(r, c, value)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


class ReadExcelTest(unittest.TestCase):

    expected = [['id', 'name', 'count'],
                ['a', 'K\xf8benhavn', 3],
                ['b', '', 7]]

    def test_same_rows_from_both_writers(self):
        for build in (build_xlsx, build_xlsx_writer):
            self.assertEqual(read_excel_rows(build([SHEET])), self.expected,
                             build.__name__)

    def test_whole_float_becomes_int(self):
        rows = [['n'], [2.0], [2.5]]
        self.assertEqual(read_excel_rows(build_xlsx([rows])),
                         [['n'], [2], [2.5]])

    def test_all_sheets(self):
        other = [['x', 'y'], ['1', '2']]
        sheets = read_excel_sheets(build_xlsx([SHEET, other]))
        self.assertEqual(len(sheets), 2)
        self.assertEqual(sheets[1], other)

    def test_short_rows_are_padded(self):
        rows = [['a', 'b', 'c'], ['1']]
        self.assertEqual(read_excel_rows(build_xlsx([rows])),
                         [['a', 'b', 'c'], ['1', '', '']])

    def test_xls_rejected(self):
        with self.assertRaises(ValueError):
            read_excel_rows(build_xls([SHEET]))

    def test_invalid_data(self):
        for data in (b'', b'not excel', b'PK\x03\x04broken'):
            with self.assertRaises(ValueError):
                read_excel_rows(data)
