''' Excel export helpers '''
import unittest
import zipfile
from io import BytesIO
from unittest.mock import Mock
from xml.etree import ElementTree

from be.ldapadmin.import_export import (
    attachment_header, set_response_attachment, excel_headers_to_object,
    sort_rows_by_group, merge_cells_by_column, generate_excel)

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def _col_index(ref):
    letters = ''.join(c for c in ref if c.isalpha())
    index = 0
    for c in letters:
        index = index * 26 + ord(c) - ord('A') + 1
    return index - 1


def read_xlsx(data):
    """ Return (rows, merged ranges) of the first sheet of an xlsx file """
    with zipfile.ZipFile(BytesIO(data)) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            for si in root.findall('x:si', NS):
                strings.append(''.join(t.text or ''
                                       for t in si.iter('{%s}t' % NS['x'])))
        sheet = ElementTree.fromstring(
            archive.read('xl/worksheets/sheet1.xml'))
    rows = []
    for row in sheet.findall('x:sheetData/x:row', NS):
        values = {}
        for cell in row.findall('x:c', NS):
            value = cell.find('x:v', NS)
            if value is None:
                continue
            if cell.get('t') == 's':
                values[_col_index(cell.get('r'))] = strings[int(value.text)]
            else:
                values[_col_index(cell.get('r'))] = value.text
        line = [''] * (max(values) + 1 if values else 0)
        for index, value in values.items():
            line[index] = value
        rows.append((int(row.get('r')) - 1, line))
    merged = [m.get('ref') for m in sheet.findall('x:mergeCells/x:mergeCell',
                                                  NS)]
    return rows, merged


class AttachmentHeaderTest(unittest.TestCase):

    def test_ascii_filename(self):
        self.assertEqual(attachment_header('users list.xlsx'),
                         'attachment; filename=users%20list.xlsx')

    def test_non_ascii_filename(self):
        self.assertEqual(attachment_header('K\xf8benhavn.xlsx'),
                         "attachment; filename*=UTF-8''K%C3%B8benhavn.xlsx")

    def test_set_response_attachment(self):
        response = Mock()
        set_response_attachment(response, 'a.xlsx', 'application/x', 12)
        headers = dict(c[0] for c in response.setHeader.call_args_list)
        self.assertEqual(headers['Content-Type'], 'application/x')
        self.assertEqual(headers['Content-Length'], 12)
        self.assertEqual(headers['Content-Disposition'],
                         'attachment; filename=a.xlsx')


class ExcelHeadersTest(unittest.TestCase):

    def test_row_to_user_info(self):
        info = excel_headers_to_object({
            'first name*': 'Anne', 'last name*': 'Tester',
            'e-mail*': 'Anne@Example.COM', 'organisation*': 'dk_org',
            'telephone number': '+45 1234', 'url': 'example.com',
        })
        self.assertEqual(info['email'], 'anne@example.com')
        self.assertEqual(info['first_name'], 'Anne')
        self.assertEqual(info['phone'], '+45 1234')
        self.assertEqual(info['organisation'], 'dk_org')
        self.assertEqual(info['full_name_native'], '')
        self.assertIsNone(info['id'])


class GenerateExcelTest(unittest.TestCase):

    def test_round_trip(self):
        data = generate_excel(
            ['Name', 'Email', 'Count'],
            [['K\xf8benhavn', b'anne@example.com', 3],
             ['Bob', 'bob@example.com', None]])
        rows, merged = read_xlsx(data)
        self.assertEqual([r for _, r in rows], [
            ['Name', 'Email', 'Count'],
            ['K\xf8benhavn', 'anne@example.com', '3'],
            ['Bob', 'bob@example.com', 'None'],
        ])
        self.assertEqual(merged, [])

    def test_header_only(self):
        rows, merged = read_xlsx(generate_excel(['A', 'B'], [[]]))
        self.assertEqual(rows[0], (0, ['A', 'B']))


class GroupedExportTest(unittest.TestCase):

    def test_sort_rows_by_group(self):
        rows = [['r1', 'zed'], ['r1', 'Anne'], ['r1', 'bob'],
                ['r2', 'Yan'], ['r2', 'carl']]
        sort_rows_by_group(rows, [0], 1)
        self.assertEqual(rows, [['r1', 'Anne'], ['r1', 'bob'], ['r1', 'zed'],
                                ['r2', 'carl'], ['r2', 'Yan']])

    def test_merge_cells_by_column(self):
        rows = [['r1', 'Role one', 'Anne'], ['r1', 'Role one', 'Bob'],
                ['r2', 'Role two', 'Carl']]

        def fiddle(wb):
            ws = wb.get_worksheet_by_name('Sheet 1')
            merge_cells_by_column(wb, ws, rows, [0, 1])

        data = generate_excel(['Role', 'Description', 'Name'], rows, fiddle)
        sheet_rows, merged = read_xlsx(data)
        self.assertEqual(sorted(merged), ['A2:A3', 'B2:B3'])
        cells = dict(sheet_rows)
        self.assertEqual(cells[1], ['r1', 'Role one', 'Anne'])
        self.assertEqual(cells[2][2], 'Bob')
        self.assertEqual(cells[3], ['r2', 'Role two', 'Carl'])
