# Copyright (c) 2013 Michael Bitzi
# Licensed under the MIT license http://opensource.org/licenses/MIT

from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals


def test(*args, **kwargs):
    return (args, kwargs)


def quit():
    exit()