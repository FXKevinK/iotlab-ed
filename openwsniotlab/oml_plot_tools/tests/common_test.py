# -*- coding:utf-8 -*-

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

import unittest

try:
    # pylint:disable=unused-import
    from cStringIO import StringIO  # noqa
except ImportError:  # Python 3
    # pylint:disable=unused-import
    from io import StringIO  # noqa

# Issues with pylint and numpy
# pylint:disable=no-member
import numpy

from oml_plot_tools import common
from oml_plot_tools import consum


MEASURE_FMT = ('{t} {type} {num} {t_s} {t_us} {measures}\n')
HEADER = 'HEADER\n' * common.OML_HEADER_LEN
CONSO_T = common.OML_TYPES['consumption']


class TestCommon(unittest.TestCase):

    def test_oml_load(self):

        meas = '1. 2. 3.'
        content = HEADER
        content += MEASURE_FMT.format(t=0.1234, type=CONSO_T, num=1,
                                      t_s=12345, t_us=678900, measures=meas)
        content += MEASURE_FMT.format(t=1.1234, type=CONSO_T, num=2,
                                      t_s=12346, t_us=678900, measures=meas)

        ret = common.oml_load(StringIO(content), 'consumption',
                              consum.MEASURES_D.values())

        expected = [(12345.6789, 'consumption', 1, 12345, 678900, 1., 2., 3.),
                    (12346.6789, 'consumption', 2, 12346, 678900, 1., 2., 3.)]
        self.assertEqual(expected, ret.tolist())
        self.assertTrue(isinstance(ret, numpy.ndarray))

    def test_oml_load_only_one(self):
        meas = '1. 2. 3.'
        content = HEADER
        content += MEASURE_FMT.format(t=0.1234, type=CONSO_T, num=1,
                                      t_s=12345, t_us=678900, measures=meas)

        ret = common.oml_load(StringIO(content), 'consumption',
                              consum.MEASURES_D.values())

        expected = [(12345.6789, 'consumption', 1, 12345, 678900, 1., 2., 3.)]
        self.assertEqual(expected, ret.tolist())
        self.assertTrue(isinstance(ret, numpy.ndarray))

    def test_oml_invalid(self):

        # invalid data
        content = HEADER + 'invalid_content'
        self.assertRaises(ValueError, common.oml_load,
                          StringIO(content), 'consumption',
                          consum.MEASURES_D.values())

        # Unknown file path
        self.assertRaises(ValueError, common.oml_load,
                          '/invalid/file/path', 'consumption',
                          consum.MEASURES_D.values())

        # skip header fail
        self.assertRaises(ValueError, common.oml_load,
                          StringIO('1 2 3'), 'consumption',
                          consum.MEASURES_D.values())

        # invalid oml 'type' file
        meas = '1. 2. 3.'
        content = HEADER
        content += MEASURE_FMT.format(t=0.1234, type=(CONSO_T + 1), num=1,
                                      t_s=12345, t_us=678900, measures=meas)
        self.assertRaises(ValueError, common.oml_load,
                          StringIO(content), 'consumption',
                          consum.MEASURES_D.values())
