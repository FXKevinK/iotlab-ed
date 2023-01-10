#!/usr/bin/python
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


"""
usage: plot_oml_consum [-h] -i DATA [-l TITLE] [-b BEGIN] [-e END] [-a] [-p]
                       [-v] [-c] [-t]

Plot iot-lab consumption OML files

optional arguments:
  -h, --help            show this help message and exit
  -i DATA, --input DATA
                        Node consumption values
  -l TITLE, --label TITLE
                        Graph title
  -b BEGIN, --begin BEGIN
                        Sample start
  -e END, --end END     Sample end

plot:
  Plot selection

  -a, --all             Plot power/voltage/current on one figure (default)
  -p, --power           Plot power
  -v, --voltage         Plot voltage
  -c, --current         Plot current
  -t, --time            Plot time verification
"""


import argparse
import sys

import matplotlib.pyplot as plt
from . import common


# Selection variables
_POWER = 'power'
_VOLTAGE = 'voltage'
_CURRENT = 'current'
_ALL = 'all'
_TIME = 'time'
_TITLE = 'Node'


MEASURES_D = common.measures_dict(
    (_POWER, float, 'Power (W)'),
    (_VOLTAGE, float, 'Voltage (V)'),
    (_CURRENT, float, 'Current (A)'),
)


def oml_load(filename):
    """ Load consumption oml file """
    data = common.oml_load(filename, 'consumption', MEASURES_D.values())
    return data


PARSER = argparse.ArgumentParser(
    prog='plot_oml_consum', description="Plot iot-lab consumption OML files")
PARSER.add_argument('-i', '--input', dest='data', type=oml_load, required=True,
                    help="Node consumption values")
PARSER.add_argument('-l', '--label', dest='title', default=_TITLE,
                    help="Graph title")
PARSER.add_argument('-b', '--begin', default=0, type=int, help="Sample start")
PARSER.add_argument('-e', '--end', default=-1, type=int, help="Sample end")

_PLOT = PARSER.add_argument_group('plot', "Plot selection")
_PLOT.add_argument('-a', '--all', dest='plot', const=_ALL,
                   action='append_const',
                   help="Plot power/voltage/current on one figure (default)")
_PLOT.add_argument('-p', '--power', dest='plot', const=_POWER,
                   action='append_const', help="Plot power")
_PLOT.add_argument('-v', '--voltage', dest='plot', const=_VOLTAGE,
                   action='append_const', help="Plot voltage")
_PLOT.add_argument('-c', '--current', dest='plot', const=_CURRENT,
                   action='append_const', help="Plot current")
_PLOT.add_argument('-t', '--time', dest='plot', const=_TIME,
                   action='append_const', help="Plot time verification")


def consumption_plot(data, title, selection):
    """ Plot consumption values according to selection

    :param data: numpy array returned by oml_read
    :param title: Subplots title base
    :param selection: with values in
        'power', 'voltage', 'current': plot on different windows
        'all': plot all three on the same window
        'time': plot time verification
    """

    # Single selection of 'p/v/c'
    for value in (_POWER, _VOLTAGE, _CURRENT):
        if value in selection:
            oml_plot(data, title, [MEASURES_D[value]])

    # Plot all on the same window
    if _ALL in selection:
        oml_plot(data, title, MEASURES_D.values())

    # Clock verification
    if 'time' in selection:
        common.oml_plot_clock(data)

    common.plot_show()


def oml_plot(data, title, meas_tuples):
    """ Plot consumption value for 'meas_tuples'

    :param data: numpy array returned by oml_read
    :param title: Subplots title base
    :param meas_tuples: numpy.dtypesplots separated on different windows
    """

    nbplots = len(meas_tuples)
    plt.figure()

    for num, meas in enumerate(meas_tuples, start=1):
        plt.subplot(nbplots, 1, num)

        _title = f'{title} {meas.name}'
        common.plot(data, _title, meas.name, meas.label)


def main(args=None):
    """ iotlab-plot consum command """
    args = args or sys.argv[1:]

    opts = PARSER.parse_args(args)
    # default to plot all
    selection = opts.plot or (_ALL)
    # select samples
    data = opts.data[opts.begin:opts.end]
    consumption_plot(data, opts.title, selection)


if __name__ == "__main__":
    main()
