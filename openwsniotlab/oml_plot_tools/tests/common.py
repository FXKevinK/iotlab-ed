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


""" Common tests functions """

import os
import math
import runpy

try:
    # pylint:disable=unused-import
    from cStringIO import StringIO  # noqa
except ImportError:  # Python 3
    # pylint:disable=unused-import
    from io import StringIO  # noqa

import mock
import matplotlib.pyplot as plt
from PIL import Image

TEST_DIR = os.path.dirname(__file__)


def test_file_path(*args):
    """ Test file path """
    return os.path.join(TEST_DIR, *args)


def help_main_and_doc(module, help_opt='--help'):
    """ Check that help message is module docstring """

    if not hasattr(module, 'main'):
        return None, None  # pragma: no cover

    help_args = [module.__name__, help_opt]
    out_msg = StringIO()

    with mock.patch('sys.argv', help_args):
        with mock.patch('sys.stderr', out_msg):
            with mock.patch('sys.stdout', out_msg):
                try:
                    runpy.run_module(module.__name__,
                                     run_name='__main__', alter_sys=True)
                except SystemExit:
                    pass

    help_msg = out_msg.getvalue().strip()
    help_doc = module.__doc__.strip()
    print(help_msg)
    print(help_doc)

    return help_msg, help_doc


def utest_help_as_doc(testcase_instance, module, *args, **kwargs):
    """ Run help_as_doc as unittest test """
    help_msg, help_doc = help_main_and_doc(module, *args, **kwargs)
    testcase_instance.assertEqual(help_msg, help_doc)


def compare_images(ref_img, tmp_img):
    """ Compare two images using PIL:
    :returns: root-mean-square of the two images

    # http://stackoverflow.com/a/1927681/395687 """
    ref_h = Image.open(ref_img).histogram()
    tmp_h = Image.open(tmp_img).histogram()
    rms = math.sqrt(sum((a-b)**2 for a, b in zip(ref_h, tmp_h))/len(ref_h))
    return rms


def utest_plot_and_compare(testcase, ref_img, threshold=0.0):
    """ Plot image and compare files.
    Keep file if they differ

    'savefig' is not determinist between hosts so allow some differences with
    threshold. Threshold choosen for png generated on Gaëtan computer
    and errors found on ci server.
    """
    tmp_img = os.path.join('/tmp', os.path.basename(ref_img))

    plt.tight_layout()
    plt.savefig(tmp_img)

    # Check files
    rms = compare_images(ref_img, tmp_img)

    msg = (
        f'{ref_img} != {tmp_img}: Root-mean-square == {rms:f} > {threshold:f}'
    )
    testcase.assertTrue(rms <= threshold, msg=msg)

    # Cleanup on success
    os.remove(tmp_img)


def assert_called_with_nparray(mock_function, np_array, *args, **kwargs):
    """Assert mock function has been called with given np_array and arguments.

    Using default mock assert_called_with failed.
    Also using numpy comparison functions did not return expected value so use
    'repr'
    """
    call_args, call_kwargs = mock_function.call_args

    call_array = call_args[0]
    call_args = call_args[1:]

    assert repr(call_array) == repr(np_array)
    assert repr(call_args) == repr(args)
    assert call_kwargs == kwargs
