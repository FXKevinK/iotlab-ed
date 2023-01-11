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
import json

import mock

from .common import (utest_help_as_doc, utest_plot_and_compare,
                     test_file_path, assert_called_with_nparray)

from .. import traj, common


def robot_get_map(site):
    """Simulate robot_get_map using examples files."""
    map_cfg = {}

    with open(test_file_path('examples', f'{site}-iotlab.png'), 'rb') as _fd:
        map_cfg['image'] = _fd.read()

    with open(test_file_path('examples', f'{site}-mapconfig.json')) as _fd:
        map_cfg['config'] = json.load(_fd)

    with open(test_file_path('examples', f'{site}-dockconfig.json')) as _fd:
        map_cfg['dock'] = json.load(_fd)

    return map_cfg


def maps_load(site):
    """Load given site map and retern mapinfo."""
    map_cfg = robot_get_map(site)
    return traj._mapinfo_from_cfg(map_cfg)  # pylint:disable=protected-access


class TestTrajectoryOmlPlot(unittest.TestCase):
    def setUp(self):
        robot_file = test_file_path('examples', 'robot.oml')
        circuit_file = test_file_path('examples', 'Jhall_w.json')

        self.data = traj.oml_load(robot_file)
        self.mapinfo = maps_load('grenoble')
        self.circuit = traj.circuit_load(circuit_file)
        self.title = "Robot"

    def test_plot_all(self):
        ref_img = test_file_path('examples', 'trajectory_all.png')
        traj.oml_plot_map(self.data, self.title, self.mapinfo, self.circuit)
        utest_plot_and_compare(self, ref_img, 11000)

    def test_plot_traj_only(self):
        ref_img = test_file_path('examples', 'trajectory_only.png')
        traj.oml_plot_map(self.data, self.title, None, None)
        utest_plot_and_compare(self, ref_img, 1500)

    def test_plot_traj_circuit(self):
        ref_img = test_file_path('examples', 'trajectory_circuit.png')
        traj.oml_plot_map(None, self.title, None, self.circuit)
        utest_plot_and_compare(self, ref_img, 1500)

    def test_plot_traj_nothing(self):
        ret = traj.oml_plot_map(None, None, None, None)
        self.assertFalse(ret)

    def test_plot_angle(self):
        ref_img = test_file_path('examples', 'trajectory_angle.png')
        traj.oml_plot_angle(self.data, self.title)
        utest_plot_and_compare(self, ref_img, 50)

    def test_plot_clock(self):
        ref_img = test_file_path('examples', 'trajectory_clock.png')
        common.oml_plot_clock(self.data)
        utest_plot_and_compare(self, ref_img, 100)


class TestTrajectory(unittest.TestCase):

    def setUp(self):
        meas_file = test_file_path('examples', 'robot.oml')
        self.data = traj.oml_load(meas_file)[0:1]

        self.title = 'TITLE_TESTS'
        self.args = ['plot_oml_consum',
                     '-i', meas_file, '--begin', '0', '--end', '1',
                     '-l', self.title]

        self.oml_plot_map = mock.patch('oml_plot_tools.traj'
                                       '.oml_plot_map').start()
        self.oml_plot_map.return_value = False
        self.oml_plot_angle = mock.patch('oml_plot_tools.traj'
                                         '.oml_plot_angle').start()
        self.oml_plot_angle.return_value = False
        self.oml_plot_clock = mock.patch('oml_plot_tools.traj'
                                         '.common.oml_plot_clock').start()
        self.oml_plot_clock.return_value = False

        self.plot_show = mock.patch('oml_plot_tools.traj'
                                    '.common.plot_show').start()

    def tearDown(self):
        mock.patch.stopall()

    def traj_main(self, *args):
        """Call traj main with given additional args."""
        with mock.patch('sys.argv', list(self.args) + list(args)):
            traj.main()

    def test_plot_traj(self):
        self.oml_plot_map.return_value = True
        self.traj_main('--traj')
        assert_called_with_nparray(self.oml_plot_map, self.data, self.title,
                                   None, None)
        self.assertFalse(self.oml_plot_angle.called)
        self.assertFalse(self.oml_plot_clock.called)
        self.assertTrue(self.plot_show.called)

    def test_plot_angle(self):
        self.oml_plot_angle.return_value = True
        self.traj_main('--angle')
        self.assertFalse(self.oml_plot_map.called)
        assert_called_with_nparray(self.oml_plot_angle, self.data, self.title)
        self.assertFalse(self.oml_plot_clock.called)
        self.assertTrue(self.plot_show.called)

    def test_plot_clock(self):
        self.oml_plot_clock.return_value = True
        self.traj_main('--time')
        self.assertFalse(self.oml_plot_map.called)
        self.assertFalse(self.oml_plot_angle.called)
        assert_called_with_nparray(self.oml_plot_clock, self.data)
        self.assertTrue(self.plot_show.called)

    def test_plot_nothing(self):
        # Traj requested but no data
        self.oml_plot_map.return_value = False
        self.args = ['plot_oml_consum']
        self.traj_main('--traj')

        assert_called_with_nparray(self.oml_plot_map, None, 'Robot',
                                   None, None)
        self.assertFalse(self.oml_plot_angle.called)
        self.assertFalse(self.oml_plot_clock.called)

    @mock.patch('iotlabcli.robot.robot_get_map', robot_get_map)
    def test_plot_mapinfo(self):
        self.args = ['plot_oml_consum']
        self.traj_main('--site-map', 'grenoble')
        self.assertTrue(self.oml_plot_map.called)


class TestDoc(unittest.TestCase):
    def test_doc(self):
        utest_help_as_doc(self, traj)
