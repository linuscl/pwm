# Copyright (c) 2013 Michael Bitzi
# Licensed under the MIT license http://opensource.org/licenses/MIT

from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import unittest

import pwm.xcb
import pwm.workspaces
import pwm.windows
from pwm.config import config
import test.util as util


class TestWorkspaces(unittest.TestCase):
    def setUp(self):
        util.setup()

        self.window = pwm.windows.Window(pwm.xcb.screen.root)
        self.workspace = pwm.workspaces.current()
        self.workspace.add_window(self.window)

    def tearDown(self):
        util.tear_down()

    def test_setup(self):
        # setup() was already called in setUp

        self.assertEqual(len(pwm.workspaces.workspaces), config.workspaces)
        self.assertEqual(pwm.workspaces.current(),
                         pwm.workspaces.workspaces[0])

        self.assertTrue(pwm.workspaces.current().active)

    def test_destroy(self):
        pwm.workspaces.destroy()
        self.assertEqual(len(pwm.workspaces.workspaces), 0)

    def test_geometry(self):
        self.assertEqual(self.workspace.x, 0)
        self.assertEqual(self.workspace.y, pwm.workspaces.bar.height)
        self.assertEqual(self.workspace.width, pwm.xcb.screen.width_in_pixels)
        self.assertEqual(
            self.workspace.height,
            pwm.xcb.screen.height_in_pixels - pwm.workspaces.bar.height)

    def test_add_window(self):
        # Window already added
        self.assertEqual(len(self.workspace.windows), 1)
        self.assertTrue(self.window in self.workspace.windows)

    def test_remove_window(self):
        win = pwm.windows.Window(pwm.xcb.screen.root)
        self.workspace.add_window(win)

        self.workspace.remove_window(self.window)
        self.assertEqual(len(self.workspace.windows), 1)

        self.workspace.remove_window(win)
        self.assertEqual(len(self.workspace.windows), 0)

    def test_show(self):
        self.workspace.show()

        self.assertTrue(self.workspace.active)
        self.assertTrue(self.window.visible)

    def test_hide(self):
        self.workspace.hide()

        self.assertFalse(self.workspace.active)
        self.assertFalse(self.window.visible)

    def test_switch_workspace(self):
        pwm.workspaces.switch(1)
        self.assertEqual(pwm.workspaces.current(),
                         pwm.workspaces.workspaces[1])
