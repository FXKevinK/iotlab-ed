# -*- coding: utf-8 -*-

# This file is a part of IoT-LAB oml-plot-tools
# Copyright (C) 2015 INRIA (Contact: admin@iot-lab.info)
# Contributor(s) : see AUTHORS file
#
# This software is governed by the CeCILL license under French law
# and abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# http://www.cecill.info.
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.


# pylint:disable=missing-docstring
# python2.6
# pylint:disable=too-many-public-methods
import unittest

import mock

from .common import (test_file_path, utest_help_as_doc,
                     utest_plot_and_compare, assert_called_with_nparray)
from .. import radio


class TestRadioOmlPlot(unittest.TestCase):

    def setUp(self):
        radio_file = test_file_path('examples', 'radio.oml')
        self.data = radio.oml_load(radio_file)
        self.title = ''

    def test_plot_all(self):
        ref_img = test_file_path('examples', 'radio_single.png')
        radio.oml_plot_rssi(self.data, self.title)
        utest_plot_and_compare(self, ref_img, 100)

    def test_plot_current(self):
        # multiple images are printed but only last one is kept
        ref_img = test_file_path('examples', 'radio_separated_last.png')
        radio.oml_plot_rssi(self.data, self.title, separated=True)
        utest_plot_and_compare(self, ref_img, 50)

    def test_plot_clock(self):
        ref_img = test_file_path('examples', 'radio_clock.png')
        radio.common.oml_plot_clock(self.data)
        utest_plot_and_compare(self, ref_img, 50)


class TestRadioPlot(unittest.TestCase):

    def setUp(self):
        meas_file = test_file_path('examples', 'radio.oml')
        self.data = radio.oml_load(meas_file)[0:1]

        self.title = 'TITLE_TESTS'
        self.args = ['plot_oml_radio',
                     '-i', meas_file, '--begin', '0', '--end', '1',
                     '-l', self.title]

        self.oml_plot_rssi = mock.patch('oml_plot_tools.radio'
                                        '.oml_plot_rssi').start()
        self.oml_plot_clock = mock.patch('oml_plot_tools.radio'
                                         '.common.oml_plot_clock').start()

    def tearDown(self):
        mock.patch.stopall()

    def radio_main(self, *args):
        """Call radio main with given additional args."""
        with mock.patch('sys.argv', list(self.args) + list(args)):
            radio.main()

    def test_plot_joined(self):
        self.radio_main('--all')
        assert_called_with_nparray(self.oml_plot_rssi, self.data, self.title)

    def test_plot_separated(self):
        self.radio_main('--plot')
        assert_called_with_nparray(self.oml_plot_rssi,
                                   self.data, self.title, separated=True)

    def test_plot_time(self):
        self.radio_main('--time')
        assert_called_with_nparray(self.oml_plot_clock, self.data)


class TestDoc(unittest.TestCase):
    def test_doc(self):
        utest_help_as_doc(self, radio)
