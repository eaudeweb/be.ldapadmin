import xlsxwriter
import logging
import urllib
from io import BytesIO
from naaya.core.utils import force_to_unicode

logger = logging.getLogger(__name__)


def attachment_header(filename):
    assert isinstance(filename, str)
    try:
        filename.decode('ascii')
    except UnicodeDecodeError:
        value = "filename*=UTF-8''%s" % urllib.quote(filename)
    else:
        value = "filename=%s" % urllib.quote(filename)
    return "attachment; " + value


def set_response_attachment(RESPONSE, filename, content_type, length=None):
    RESPONSE.setHeader('Content-Type', content_type)
    if length is not None:
        RESPONSE.setHeader('Content-Length', length)
    RESPONSE.setHeader('Pragma', 'public')
    RESPONSE.setHeader('Cache-Control', 'max-age=0')
    RESPONSE.setHeader('Content-Disposition', attachment_header(filename))


def excel_headers_to_object(properties):
    """ Converts row data to object, according to header keys """
    # main purpose is to save code lines in logic
    return {
        'id': properties.get('user id'),
        'password': str(properties.get('password')),
        'email': properties.get('e-mail*').lower(),
        'first_name': properties.get('first name*'),
        'last_name': properties.get('last name*'),
        'full_name_native': properties.get('full name (native language)', ''),
        'search_helper': properties.get(
            'search helper (ascii characters only!)', ''),
        'job_title': properties.get('job title'),
        'url': properties.get('url'),
        'postal_address': properties.get('postal address'),
        'phone': properties.get('telephone number*'),
        'mobile': properties.get('mobile telephone number'),
        'fax': properties.get('fax number'),
        'organisation': properties.get('organisation*'),
        'department': properties.get('department'),
        # not present in Circa schema
        # 'reasonToCreate': properties.get('reason to create*')
    }


def merge_cells_by_column(wb, ws, rows, merge_columns):
    """
    Merge cells in specified columns where consecutive rows have the same value.

    Args:
        wb: xlsxwriter Workbook object
        ws: xlsxwriter Worksheet object
        rows: List of row data
        merge_columns: List of column indices to merge
    """
    # Create centered format for merged cells
    style_center = wb.add_format({
        'align': 'center',
        'valign': 'vcenter'
    })

    current_slice_start = 0
    len_rows = len(rows)
    for i in range(0, len_rows):
        current_role = rows[i][0]
        next_role = rows[i+1][0] if i + 1 < len_rows else None
        if next_role != current_role:
            current_slice_end = i

            # account for header row (add offset)
            offset_slice_range_start = current_slice_start + 1
            offset_slice_range_end = current_slice_end + 1

            for col_idx in merge_columns:
                # Ensure the value is unicode for xlsxwriter
                cell_value = force_to_unicode(rows[i][col_idx])

                if offset_slice_range_start == offset_slice_range_end:
                    # Single cell, just write it
                    ws.write(offset_slice_range_start, col_idx,
                           cell_value, style_center)
                else:
                    # Merge multiple cells
                    ws.merge_range(
                        offset_slice_range_start, col_idx,
                        offset_slice_range_end, col_idx,
                        cell_value,
                        style_center
                    )

            # start next slice at next row
            current_slice_start = i + 1


def generate_excel(header, rows, fiddle_workbook=None):
    output = BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Sheet 1')

    # Define formats
    header_format = wb.add_format({'bold': True})
    wrap_format = wb.add_format({'text_wrap': True})

    # Set column widths
    for col in range(0, len(header)):
        ws.set_column(col, col, 35)

    # Write header row
    row = 0
    for col in range(0, len(header)):
        ws.write(row, col, force_to_unicode(header[col]), header_format)

    # Write data rows
    for item in rows:
        row += 1
        for col in range(0, len(item)):
            value = force_to_unicode(item[col])
            if '\n' in value:
                ws.write(row, col, value, wrap_format)
            else:
                ws.write(row, col, value)

    if fiddle_workbook:
        fiddle_workbook(wb)

    wb.close()
    return output.getvalue()
