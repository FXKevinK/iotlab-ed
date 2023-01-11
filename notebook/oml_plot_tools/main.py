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

"""Main parser."""

import sys
from argparse import ArgumentParser

import oml_plot_tools.consum
import oml_plot_tools.radio
import oml_plot_tools.traj


def main(args=None):
    """'iotlab' main function."""
    args = args or sys.argv[1:]

    commands = {
        'consum': oml_plot_tools.consum.main,
        'radio': oml_plot_tools.radio.main,
        'traj': oml_plot_tools.traj.main,
        'help': None
    }

    parser = ArgumentParser()
    parser.add_argument('command', nargs='?',
                        choices=commands.keys(), default='help')
    commands['help'] = lambda args: parser.print_help()

    opts, args = parser.parse_known_args(args)

    return commands[opts.command](args)
