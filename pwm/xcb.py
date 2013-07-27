# Copyright (c) 2013 Michael Bitzi
# Licensed under the MIT license http://opensource.org/licenses/MIT

from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import struct
import xcb
import xcb.xproto as xproto

conn = None
core = None
screen = None


def connect(display=None):
    """Connect to the X server."""

    global conn
    conn = xcb.connect(display)

    global core
    core = conn.core

    setup = conn.get_setup()

    global screen
    screen = setup.roots[0]


def disconnect():
    """Disconnect from the X server."""
    conn.disconnect()


def setup_root_window():
    """Set up the root window."""

    root_event_mask = (xproto.EventMask.StructureNotify |
                       xproto.EventMask.SubstructureNotify |
                       xproto.EventMask.SubstructureRedirect |
                       xproto.EventMask.EnterWindow |
                       xproto.EventMask.LeaveWindow)

    cookie = core.ChangeWindowAttributesChecked(
        screen.root,
        xproto.CW.EventMask, [root_event_mask])
    cookie.check()


#
# From Qtile
#
class MaskMap:
    """A general utility class that encapsulates the way the mask/value idiom
    works in xpyb. It understands a special attribute _maskvalue on
    objects, which will be used instead of the object value if present.
    This lets us passin a Font object, rather than Font.fid, for example.
    """
    def __init__(self, obj):
        self.mmap = []
        for i in dir(obj):
            if not i.startswith("_"):
                self.mmap.append((getattr(obj, i), i.lower()))
        self.mmap.sort()

    def __call__(self, **kwargs):
        """kwargs: keys should be in the mmap name set
        Returns a (mask, values) tuple.
        """
        mask = 0
        values = []
        for m, s in self.mmap:
            if s in kwargs:
                val = kwargs.get(s)
                if val is not None:
                    mask |= m
                    values.append(getattr(val, "_maskvalue", val))
                del kwargs[s]
        if kwargs:
            raise ValueError("Unknown mask names: %s" % kwargs.keys())
        return mask, values

configure_mask = MaskMap(xproto.ConfigWindow)
attribute_mask = MaskMap(xproto.CW)
gc_mask = MaskMap(xproto.GC)


def create_gc():
    """Create a new graphics context"""
    gc = conn.generate_id()

    mask, values = gc_mask(
        foreground=screen.white_pixel,
        background=screen.black_pixel,
        graphicsexposures=0)

    core.CreateGC(gc, screen.root, mask, values)

    return gc

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
    if property_reply.format == 8:
        if 0 in property_reply.value[:-1]:
            ret = []
            s = []
            for o in property_reply.value:
                if o == 0:
                    ret.append(''.join(s))
                    s = []
                else:
                    s.append(chr(o))
        else:
            ret = str(property_reply.value.buf())
            if len(property_reply.value) > 0 and 0 == property_reply.value[-1]:
                ret = ret[:-1]

        return ret
    elif property_reply.format in (16, 32):
        return list(struct.unpack('I' * property_reply.value_len,
                                  property_reply.value.buf()))

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
    if isinstance(atom, basestring):
        atom = get_atom(atom)
    return core.GetProperty(False, window, atom,
                            xcb.xproto.GetPropertyType.Any, 0,
                            2 ** 32 - 1)


def get_property_unchecked(window, atom):
    """
    Abstracts the process of issuing a GetPropertyUnchecked request.

    You'll typically want to call the ``reply`` method on the return value of
    this function, and pass that result to
    'get_property_value' so that the data is nicely formatted.

    :param window: A window identifier.
    :type window: int
    :param atom: An atom identifier.
    :type atom: int OR str
    :rtype: xcb.xproto.GetPropertyCookie
    """
    if isinstance(atom, basestring):
        atom = get_atom(atom)
    return core.GetPropertyUnchecked(False, window, atom,
                                     xcb.xproto.GetPropertyType.Any, 0,
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
    atom = core.InternAtomUnchecked(only_if_exists, len(atom_name),
                                    atom_name)
    return AtomCookie(atom)


def __get_atom_name_cookie(atom):
    """
    Private function that issues the xpyb call to get an ATOM identifier's
    name.

    :type atom: int
    :rtype: xcb.xproto.GetAtomNameCookie
    """
    return AtomNameCookie(core.GetAtomNameUnchecked(atom))
