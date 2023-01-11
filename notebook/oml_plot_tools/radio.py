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
usage: plot_oml_radio [-h] -i DATA [-l TITLE] [-b BEGIN] [-e END] [-a] [-p]
                      [-t]

Plot iot-lab radio OML files

optional arguments:
  -h, --help            show this help message and exit
  -i DATA, --input DATA
                        Node radio values
  -l TITLE, --label TITLE
                        Graph title
  -b BEGIN, --begin BEGIN
                        Sample start
  -e END, --end END     Sample end

plot:
  Plot selection

  -a, --all             Plot all channels in one window (default)
  -p, --plot            Plot channels in different windows
  -t, --time            Plot time verification
"""


import argparse
import sys

import matplotlib.pyplot as plt
from . import common

MEASURES_D = common.measures_dict(
    ('channel', int, 'Channel'),
    ('rssi', int, 'RSSI (dBm)'),
)


def oml_load(filename):
    """ Load radio oml file """
    data = common.oml_load(filename, 'radio', MEASURES_D.values())
    return data


# Selection variables
_JOINED = 'joined'
_SEPARATED = 'separated'
_TIME = 'time'


PARSER = argparse.ArgumentParser(
    prog='plot_oml_radio', description="Plot iot-lab radio OML files")
PARSER.add_argument('-i', '--input', dest='data', type=oml_load, required=True,
                    help="Node radio values")
PARSER.add_argument('-l', '--label', dest='title', default="Node",
                    help="Graph title")
PARSER.add_argument('-b', '--begin', default=0, type=int, help="Sample start")
PARSER.add_argument('-e', '--end', default=-1, type=int, help="Sample end")

_PLOT = PARSER.add_argument_group('plot', "Plot selection")
_PLOT.add_argument('-a', '--all', dest='plot', const=_JOINED,
                   action='append_const',
                   help="Plot all channels in one window (default)")
_PLOT.add_argument('-p', '--plot', dest='plot', const=_SEPARATED,
                   action='append_const',
                   help="Plot channels in different windows")
_PLOT.add_argument('-t', '--time', dest='plot', const=_TIME,
                   action='append_const', help="Plot time verification")


def radio_plot(data, title, selection):
    """ Plot radio values according to selection

    :param data: numpy array returnel by oml_read
    :param title: Subplots title base
    :param selection: with values in
        'joined': plot on the same window
        'separated': plot on different windows
        'time': plot time verification
    """

    if _JOINED in selection:
        oml_plot_rssi(data, title)
    if _SEPARATED in selection:
        oml_plot_rssi(data, title, separated=True)

    # Clock verification
    if _TIME in selection:
        common.oml_plot_clock(data)

    common.plot_show()


def list_channels(data):
    """ List radio channels used in data """
    channels = list(set(data['channel']))
    return sorted(channels)


def with_channel(data, channel):
    """ Extract data where measured channel == `channel` """
    select = data['channel'] == channel
    return data[select]


def oml_plot_rssi(data, title, separated=False):
    """ Plot rssi for all channels.

    :param data: numpy array returned by oml_read
    :param title: Subplots title base
    :param separated: plots separated on different windows
    """

    channels = list_channels(data)
    nbplots = len(channels)
    meas = MEASURES_D['rssi']

    # Only window for all
    if not separated:
        plt.figure()

    for num, channel in enumerate(channels, start=1):
        # Select data for channel
        cdata = with_channel(data, channel)
        _title = f'{title} Channel {channel}'

        # One window per plot
        if separated:
            plt.figure()

        plt.subplot(nbplots, 1, num)
        common.plot(cdata, _title, meas.name, meas.label)


def main(args=None):
    """ iotlab-plot radio command """
    args = args or sys.argv[1:]

    opts = PARSER.parse_args(args)
    # default to plot all
    selection = opts.plot or (_JOINED)
    # select samples
    data = opts.data[opts.begin:opts.end]
    radio_plot(data, opts.title, selection)


if __name__ == "__main__":
    main()
