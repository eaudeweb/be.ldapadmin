import xlsxwriter
import logging
import urllib
from StringIO import StringIO
from io import BytesIO

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


def generate_excel(header, rows):
    output = BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Sheet 1')
    ws.set_column('A:G', 30)
    ws.set_column(1, 1, 20)
    ws.set_column(2, 2, 50)
    ws.set_column(3, 4, 20)
    style = wb.add_format()
    bold = wb.add_format({'bold': True})
    wrapstyle = wb.add_format({'text_wrap': True})

    row = 0
    for col in range(0, len(header)):
        ws.write(row, col, header[col].decode('utf-8'), bold)
    for item in rows:
        row += 1
        for col in range(0, len(item)):
            if '\n' in item[col]:
                ws.write(row, col, item[col].decode('utf-8'), wrapstyle)
            else:
                ws.write(row, col, item[col].decode('utf-8'), style)
    wb.close()
    return output.getvalue()
