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
from .. import consum, common


class TestConsumptionOmlPlot(unittest.TestCase):

    def setUp(self):
        conso_file = test_file_path('examples', 'consumption.oml')
        self.data = consum.oml_load(conso_file)
        self.title = 'Node'

    def test_plot_all(self):
        ref_img = test_file_path('examples', 'consumption_all.png')
        consum.oml_plot(self.data, self.title, consum.MEASURES_D.values())

        utest_plot_and_compare(self, ref_img, 150)

    def test_plot_current(self):
        ref_img = test_file_path('examples', 'consumption_current.png')
        consum.oml_plot(self.data, self.title, [consum.MEASURES_D['current']])
        utest_plot_and_compare(self, ref_img, 100)

    def test_plot_clock(self):
        ref_img = test_file_path('examples', 'consumption_clock.png')
        consum.common.oml_plot_clock(self.data)
        utest_plot_and_compare(self, ref_img, 50)


class TestConsumptionPlot(unittest.TestCase):

    def setUp(self):
        meas_file = test_file_path('examples', 'consumption.oml')
        self.data = consum.oml_load(meas_file)[0:1]

        self.title = 'TITLE_TESTS'
        self.args = ['plot_oml_consum',
                     '-i', meas_file, '--begin', '0', '--end', '1',
                     '-l', self.title]

        self.oml_plot = mock.patch('oml_plot_tools.consum.oml_plot').start()
        self.oml_plot_clock = mock.patch('oml_plot_tools.consum'
                                         '.common.oml_plot_clock').start()

    def tearDown(self):
        mock.patch.stopall()

    def consum_main(self, *args):
        """Call consumption main with given additional args."""
        with mock.patch('sys.argv', list(self.args) + list(args)):
            consum.main()

    def test_plot_selection(self):
        # Plot one selection after the other
        self.consum_main('-p')
        assert_called_with_nparray(
            self.oml_plot,
            self.data, self.title,
            [common.MeasureTuple('power', float, 'Power (W)')])

        self.consum_main('-v')
        assert_called_with_nparray(
            self.oml_plot,
            self.data, self.title,
            [common.MeasureTuple('voltage', float, 'Voltage (V)')])

        self.consum_main('-c')
        assert_called_with_nparray(
            self.oml_plot,
            self.data, self.title,
            [common.MeasureTuple('current', float, 'Current (A)')])

        # Plot only once per entry
        self.oml_plot.reset_mock()
        self.consum_main('-c', '-v', '-p', '-p')
        self.assertEqual(self.oml_plot.call_count, 3)

    def test_plot_all(self):
        self.consum_main('-a')
        assert_called_with_nparray(
            self.oml_plot,
            self.data, self.title,
            consum.MEASURES_D.values())

    def test_plot_default_all(self):
        self.consum_main()
        assert_called_with_nparray(
            self.oml_plot,
            self.data, self.title,
            consum.MEASURES_D.values())

    def test_plot_time(self):
        self.consum_main('-t')
        assert_called_with_nparray(self.oml_plot_clock, self.data)


class TestDoc(unittest.TestCase):
    def test_doc(self):
        utest_help_as_doc(self, consum)
