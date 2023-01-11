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

""" Test the iotlabcli.experiment_parser module """

import pytest

from mock import patch

import oml_plot_tools.main as main_parser


@pytest.mark.parametrize('entry',
                         ['consum', 'radio', 'traj'])
def test_main_parser(entry):
    """ Experiment parser """
    with patch(f'oml_plot_tools.{entry}.main') as entrypoint_func:
        main_parser.main([entry, '-i', '123'])
        entrypoint_func.assert_called_with(['-i', '123'])
