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

""" Common functions for all oml types """

# Issues with numpy
# pylint:disable=no-member

from collections import namedtuple, OrderedDict

import numpy
import matplotlib.pyplot as plt

OML_HEADER_LEN = 9

OML_TYPES = {
    'consumption': 1,
    'radio': 2,
    'event': 3,
    'sniffer': 4,
    'robot_pose': 10,
}

TIMESTAMP_LABEL = 'Sample Time (sec)'
OML_FIELDS = [
    ('timestamp', float),
    ('type', numpy.str_, 16),
    ('num', int),
    ('t_s', int),
    ('t_us', int),
]

MeasureTuple = namedtuple('MeasureTuple', ['name', 'type', 'label'])


def measures_dict(*measures_tuples):
    """ Create a dict of 'MeasuresTuple' with given measures """
    measures_list = [(m[0], MeasureTuple(*m)) for m in measures_tuples]
    return OrderedDict(measures_list)


def oml_load(filename, meas_type, measures):
    """ Load oml file
    :returns: numpy array
    :measures: list of MeasureTuple """

    meas_dtypes = [(m.name, m.type) for m in measures]

    try:
        data = _oml_read(filename, meas_type, meas_dtypes)
    except IOError as err:
        raise ValueError(f"Error opening oml file:\n{err}\n")
    except (ValueError, StopIteration, IndexError) as err:
        raise ValueError(f"Error reading oml file:\n{err}\n")
    except TypeError as err:
        raise ValueError(f"{err}")

    # No error when only one value
    data = numpy.atleast_1d(data)

    # No empty measures
    # I think not reproducible anymore with genfromtxt however.
    if array_empty(data):  # pragma: no cover
        raise ValueError("No values, not an oml file")

    return data


def oml_plot_clock(data, title='Clock time verification'):
    """ Print clock diff between measures
    :params data: oml_load returned array
    """
    time = data['timestamp']
    clock_diff = numpy.diff(time) * 1000

    print(f'Time from {time[0]:f} to {time[-1]:f}')
    print('NB Points      =', len(time))
    print('Duration    (s)=', time[-1] - time[0])
    print('Steptime   (ms)=', 1000 * (time[-1] - time[0]) / len(time))
    print('Clock mean (ms)=', numpy.mean(clock_diff))
    print('Clock std  (ms)=', numpy.std(clock_diff))
    print('Clock max  (ms)=', numpy.max(clock_diff))
    print('Clock min  (ms)=', numpy.min(clock_diff))

    plt.figure()
    plt.title(title)
    plt.grid()
    plt.plot(clock_diff)

    return True


def plot(data, title, field, ylabel, xlabel=TIMESTAMP_LABEL):
    """ Plot data """
    plt.title(title)
    plt.grid()
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.plot(data['timestamp'], data[field])


def plot_show():
    """Show image."""
    plt.tight_layout()
    plt.show()


# Help functions


def _oml_read(filename, meas_type, fields_dtypes=()):
    """ Read oml file
    :measures: list of MeasureTuple """

    # Select values
    dtypes = OML_FIELDS + list(fields_dtypes)
    names = [entry[0] for entry in dtypes]

    # Read values from file
    c_meas_type = {names.index('type'): _valid_oml_f(meas_type)}
    data = numpy.genfromtxt(filename, skip_header=OML_HEADER_LEN, names=names,
                            dtype=dtypes, converters=c_meas_type,
                            invalid_raise=False)

    # Update 'timestamp' field with the cn calculated timestamp
    for row in numpy.nditer(data, op_flags=['readwrite']):
        timestamp = row['t_s'] + row['t_us'] / 1e6
        row['timestamp'] = timestamp

    return data


def _valid_oml_f(meas_type):
    """ Return a function that validates oml type """
    def _validate(value):
        """ Check that 'meas_type' column matchs requested """
        value = int(value)
        if int(value) == OML_TYPES[meas_type]:
            return meas_type
        raise TypeError(f"OML file is not: {meas_type}")
    return _validate


def array_empty(array):
    """Test if array is not None or not empty."""
    return array is None or len(array) == 0
