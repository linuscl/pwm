# Copyright (c) 2013 Michael Bitzi
# Licensed under the MIT license http://opensource.org/licenses/MIT

from pwm.ffi.xcb import xcb


class Cursor:
    fleur = 52
    left_ptr = 68
    sizing = 120
    bottom_left_corner = 12
    bottom_right_corner = 14
    top_left_corner = 134
    top_right_corner = 136
    double_arrow_horiz = 108
    double_arrow_vert = 116


def setup_root_window():
    mask_values = (xcb.EVENT_MASK_STRUCTURE_NOTIFY |
                   xcb.EVENT_MASK_SUBSTRUCTURE_NOTIFY |
                   xcb.EVENT_MASK_SUBSTRUCTURE_REDIRECT |
                   xcb.EVENT_MASK_ENTER_WINDOW |
                   xcb.EVENT_MASK_LEAVE_WINDOW)

    cookie = xcb.core.change_window_attributes_checked(
        xcb.screen.root,
        *xcb.mask([(xcb.CW_EVENT_MASK, mask_values)]))

    cookie.check()

    # We have to set the cursor now, otherwise it will not show up until the
    # first client is launched.
    set_root_cursor(Cursor.left_ptr)


def set_root_cursor(cursor):
    fid = xcb.core.generate_id()
    xcb.core.open_font(fid, len("cursor"), "cursor".encode("UTF-8"))

    cid = xcb.core.generate_id()
    xcb.core.create_glyph_cursor(cid, fid, fid, cursor, cursor+1,
                                 0, 0, 0, 65535, 65535, 65535)
    xcb.core.change_window_attributes(xcb.screen.root,
                                      *xcb.mask((xcb.CW_CURSOR, cid)))

    xcb.core.free_cursor(cid)
    xcb.core.close_font(fid)


def get_wm_normal_hints(wid):
    cookie = xcb.core.icccm_get_wm_normal_hints(wid).value

    hints = xcb.ffi.new("xcb_size_hints_t*")
    xcb.core.icccm_get_wm_normal_hints_reply(cookie, hints, xcb.ffi.NULL)

    return hints


#
# From xpybutil
# https://github.com/BurntSushi/xpybutil/blob/master/xpybutil/util.py
#

__atom_cache = {}
__atom_nm_cache = {}


class Cookie(object):
    """
    The base Cookie class. The role of a cookie is to serve as an intermediary
    between you and the X server. After calling one of the many functions
    in the ewmh or icccm modules, the X server is typically not contacted
    immediately. Usually, you'll need to call the 'check()' or 'reply()'
    methods on the cookie returned by one of the functions in the ewmh or
    icccm modules. (Alternatively, you could flush the X buffer using
    ``conn_obj.flush()``.)
    """
    def __init__(self, cookie):
        self.cookie = cookie

    def check(self):
        return self.cookie.check()


class PropertyCookie(Cookie):
    """
    A regular property cookie that uses 'get_property_value' to return a nicer
    version to you. (Instead of raw X data.)
    """
    def reply(self):
        return get_property_value(self.cookie.reply())


class PropertyCookieSingle(Cookie):
    """
    A cookie that should only be used when one is guaranteed a single logical
    result. Namely, 'get_property_value' will be stupid and return a single
    list. This class checks for that, and takes the head of that list.
    """
    def reply(self):
        ret = get_property_value(self.cookie.reply())

        if ret and isinstance(ret, list) and len(ret) == 1:
            return ret[0]
        return ret


class AtomCookie(Cookie):
    """
    Pulls the ATOM identifier out of the reply object.
    """
    def reply(self):
        return self.cookie.reply().atom


class AtomNameCookie(Cookie):
    """
    Converts the null terminated list of characters (that represents an
    ATOM name) to a string.
    """
    def reply(self):
        return str(self.cookie.reply().name.buf())


def get_property_reply_value(wid, atom):
    return get_property_value(get_property(wid, atom).reply())


def get_property_value(property_reply):
    """
    A function that takes a property reply object, and turns its value into
    something nice for us.

    In particular, if the format of the reply is '8', then assume that it
    is a string. Moreover, it could be a list of strings that are null
    terminated. In this case, return a list of Python strings. Otherwise, just
    convert it to a string and remove the null terminator if it exists.

    Otherwise, the format must be a list of integers that has to be unpacked.
    Sometimes, these integers are ATOM identifiers, so it is useful to map
    'get_atom_name' over this list if that's the case.

    :param property_reply: An object returned by a cookie's "reply" method.
    :type property_reply: xcb.xproto.GetPropertyReply
    :return: Either a string, a list of strings or a list of integers depending
             upon the format of the property reply.
    """
    value = xcb.get_property_value(property_reply)

    if property_reply.format == 8:
        value = xcb.ffi.cast("char*", value)

        #if 0 in value[:-1]:
        #    ret = []
        #    s = []
        #    for o in value:
        #        if o == 0:
        #            ret.append(''.join(s))
        #            s = []
        #        else:
        #            s.append(chr(o))
        #else:
        ret = xcb.ffi.string(value, property_reply.value_len).decode("UTF-8")

        return ret
    elif property_reply.format in (16, 32):
        value = xcb.ffi.cast("uint%d_t*" % property_reply.format, value)
        return [value[i] for i in range(property_reply.value_len)]

    return None


def get_property(window, atom):
    """
    Abstracts the process of issuing a GetProperty request.

    You'll typically want to call the ``reply`` method on the return value of
    this function, and pass that result to
    'get_property_value' so that the data is nicely formatted.

    :param window: A window identifier.
    :type window: int
    :param atom: An atom identifier.
    :type atom: int OR str
    :rtype: xcb.xproto.GetPropertyCookie
    """
    if isinstance(atom, str):
        atom = get_atom(atom)
    return xcb.core.get_property(False, window, atom,
                                 xcb.GET_PROPERTY_TYPE_ANY, 0,
                                 2 ** 32 - 1)


def build_atom_cache(atoms):
    """
    Quickly builds a cache of ATOM names to ATOM identifiers (and the reverse).
    You'll only need to use this function if you're using atoms not defined in
    the ewmh, icccm or motif modules. (Otherwise, those modules will build this
    cache for you.)

    The 'get_atom' and 'get_atom_name' function automatically use this cache.

    :param atoms: A list of atom names.
    :rtype: void
    """
    global __atom_cache, __atom_nm_cache

    for atom in atoms:
        __atom_cache[atom] = __get_atom_cookie(atom, only_if_exists=False)
    for atom in __atom_cache:
        if isinstance(__atom_cache[atom], AtomCookie):
            __atom_cache[atom] = __atom_cache[atom].reply()

    __atom_nm_cache = dict((v, k) for k, v in __atom_cache.iteritems())


def get_atom(atom_name, only_if_exists=False):
    """
    Queries the X server for an ATOM identifier using a name. If we've already
    cached the identifier, then we don't contact the X server.

    If the identifier is not cached, it is added to the cache.

    If 'only_if_exists' is false, then the atom is created if it does not exist
    already.

    :param atom_name: An atom name.
    :type atom_name: str
    :param only_if_exists: If false, the atom is created if it didn't exist.
    :type only_if_exists: bool
    :return: ATOM identifier.
    :rtype: int
    """
    global __atom_cache

    a = __atom_cache.setdefault(atom_name,
                                __get_atom_cookie(atom_name,
                                                  only_if_exists).reply())
    if isinstance(a, AtomCookie):
        a = a.reply()

    return a


def get_atom_name(atom):
    """
    Queries the X server for an ATOM name using the specified identifier.
    If we've already cached the name, then we don't contact the X server.

    If the atom name is not cached, it is added to the cache.

    :param atom: An atom identifier.
    :type atom: int
    :return: ATOM name.
    :rtype: str
    """
    global __atom_nm_cache

    a = __atom_nm_cache.setdefault(atom, __get_atom_name_cookie(atom).reply())

    if isinstance(a, AtomNameCookie):
        a = a.reply()

    return a


def __get_atom_cookie(atom_name, only_if_exists=False):
    """
    Private function that issues the xpyb call to intern an atom.

    :type atom_name: str
    :type only_if_exists: bool
    :rtype: xcb.xproto.InternAtomCookie
    """
    atom = xcb.core.intern_atom_unchecked(only_if_exists, len(atom_name),
                                          atom_name.encode("UTF-8"))
    return AtomCookie(atom)


def __get_atom_name_cookie(atom):
    """
    Private function that issues the xpyb call to get an ATOM identifier's
    name.

    :type atom: int
    :rtype: xcb.xproto.GetAtomNameCookie
    """
    return AtomNameCookie(xcb.core.get_atom_name_unchecked(atom))
