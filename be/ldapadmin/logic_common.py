from email.message import Message
try:
    from z3c.pt.pagetemplate import PageTemplateFile
except ImportError:
    from zope.pagetemplate.pagetemplatefile import PageTemplateFile


def _get_user_password(request):
    return request.AUTHENTICATED_USER.__


def logged_in_user(request):
    ''' return the id of the authenticated user '''
    user_id = ''

    if _is_authenticated(request):
        user_id = request.AUTHENTICATED_USER.getId()

    return user_id


def _session_pop(request, name, default):
    session = request.SESSION
    if name in session.keys():
        value = session[name]
        del session[name]
        return value
    else:
        return default


def _create_plain_message(body_bytes):
    message = Message()
    message.set_payload(body_bytes)
    return message


def _is_authenticated(request):
    ''' check if the user is authenticated '''
    return 'Authenticated' in request.AUTHENTICATED_USER.getRoles()


# pylint: disable=dangerous-default-value
def load_template(name, context=None, _memo={}):
    ''' load the main template '''
    if name not in _memo:
        tpl = PageTemplateFile(name)

        if context is not None:
            bound = tpl.bind(context)
            _memo[name] = bound
        else:
            _memo[name] = tpl

    return _memo[name]


def splitlines(value):
    if isinstance(value, basestring):
        value = value.replace(',', '\n').splitlines()
        value = [val.strip() for val in value]
    if not isinstance(value, list):
        raise NotImplementedError
    return value
