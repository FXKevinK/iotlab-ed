"""
Trickle Timer: IETF RFC 6206 (https://tools.ietf.org/html/rfc6206)
"""
from __future__ import absolute_import
from __future__ import division

from builtins import str
from builtins import object
from past.utils import old_div
import math
import random

import SimEngine
from . import MoteDefines as d


class ACPBTrickle(object):
    STATE_STOPPED = u'stopped'
    STATE_RUNNING = u'running'

    def __init__(self, i_min, i_max, k, callback, mote):
        assert isinstance(i_min, (int, int))
        assert isinstance(i_max, (int, int))
        assert isinstance(k, (int, int))
        assert callback is not None

        # shorthand to singletons
        self.engine = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()

        # constants of this timer instance
        # min_interval is expected to given in milliseconds
        # max_interval is expected to be described as a number of doublings of the
        # minimum interval size
        self.min_interval = i_min
        self.max_interval = self.min_interval * pow(2, i_max)
        self.redundancy_constant = k
        self.unique_tag_base = str(id(self))

        # variables
        self.counter = 0
        self.interval = 0
        self.user_callback = callback
        self.state = self.STATE_STOPPED

        self.i_max = i_max
        self.flag = self.m = -1
        self.Nnbr = 0
        self.mote = mote
        self.kmax = 10

        self.transmitted = self.suppressed = 0

    @property
    def is_running(self):
        return self.state == self.STATE_RUNNING

    def start(self):
        # Section 4.2:
        #   1.  When the algorithm starts execution, it sets I to a value in
        #       the range of [Imin, Imax] -- that is, greater than or equal to
        #       Imin and less than or equal to Imax.  The algorithm then begins
        #       the first interval.
        self.state = self.STATE_RUNNING
        self.interval = random.randint(self.min_interval, self.max_interval)
        self._start_next_interval()

    def stop(self):
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_i')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_t')
        self.state = self.STATE_STOPPED

    def reset(self):
        if self.state == self.STATE_STOPPED:
            return

        # this method is expected to be called in an event of "inconsistency"
        #
        # Section 4.2:
        #   6.  If Trickle hears a transmission that is "inconsistent" and I is
        #       greater than Imin, it resets the Trickle timer.  To reset the
        #       timer, Trickle sets I to Imin and starts a new interval as in
        #       step 2.  If I is equal to Imin when Trickle hears an
        #       "inconsistent" transmission, Trickle does nothing.  Trickle can
        #       also reset its timer in response to external "events".
        if self.min_interval < self.interval:
            self.interval = self.min_interval
            # Algorithm 1 (a)
            self.flag = self.m
            self.m = -1
            self.transmitted = self.suppressed = 0
            self._start_next_interval()
        else:
            # if the interval is equal to the minimum value, do nothing
            pass

    def increment_counter(self):
        # this method is expected to be called when a "consistent" transmission
        # is heard.
        #
        # Section 4.2:
        #   3.  Whenever Trickle hears a transmission that is "consistent", it
        #       increments the counter c.
        self.counter += 1

        # Algorithm 1 (b)
        if self.flag != -1:
            self.interval = self.min_interval * pow(2, self.flag)
            self.m = self.flag
            self.flag = -1

    # Algoritma 3
    def calculate_interval_t(self):
        # t = old_div((1 + random.random()) * self.interval, 2)
        # t_start = old_div(self.interval, 2)
        # t_end = self.interval

        slotframe_len = self.settings.tsch_slotframeLength * \
            self.settings.tsch_slotDuration * 1000  # convert to ms
        self.Ncell = int(math.ceil(old_div(self.interval, slotframe_len)))
        self.Nnbr = len(self.mote.rpl.of.neighbors)

        if self.interval == self.min_interval or self.suppressed != 0:
            self.t_start = 0
            self.t_end = old_div(
                self.Ncell, 2) - (old_div(old_div(self.Ncell, 2), self.Nnbr + 1) * self.suppressed)
        elif self.transmitted != 0:
            self.t_start = old_div(
                self.Ncell, 2) + (old_div(self.Nnbr + 1, old_div(self.Ncell, 2)) * self.transmitted)
            self.t_end = self.Ncell

        t = random.randint(self.t_start, self.t_end)
        interval = (t + 1) * slotframe_len

        return interval

    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self.counter = 0

        self.m += 1
        if self.i_max < self.m:
            self.m = self.i_max
        assert self.m > -1 and self.m <= self.i_max

        t = self.calculate_interval_t()

        self._schedule_event_at_t(t)
        self._schedule_event_at_end_of_interval()

    # Algorithm 2
    def calculate_k(self):
        self.Nnbr = len(self.mote.rpl.of.neighbors)
        if self.interval == self.min_interval:
            k = min(self.Nnbr + 1, self.kmax)
        elif self.interval > self.min_interval and self.m <= old_div(self.i_max, 2):
            k = min(math.ceil(self.Nnbr + 1 / 2), self.kmax)
        else:
            k = min(self.Nnbr + 1, self.kmax)
        return k

    def _schedule_event_at_t(self, t):
        # select t in the range [I/2, I), where I == self.current_interval
        #
        # Section 4.2:
        #   2.  When an interval begins, Trickle resets c to 0 and sets t to a
        #       random point in the interval, taken from the range [I/2, I),
        #       that is, values greater than or equal to I/2 and less than I.
        #       The interval ends at I.
        slot_len = self.settings.tsch_slotDuration * 1000  # convert to ms
        asn = self.engine.getAsn() + int(math.ceil(old_div(t, slot_len)))
        if asn == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn = self.engine.getAsn() + 1

        def _callback():
            self.redundancy_constant = self.calculate_k()
            if self.counter < self.redundancy_constant:
                #  Section 4.2:
                #    4.  At time t, Trickle transmits if and only if the
                #        counter c is less than the redundancy constant k.
                self.transmitted += 1
                self.user_callback()
            else:
                # do nothing
                self.suppressed += 1

        self.engine.scheduleAtAsn(
            asn=asn,
            cb=_callback,
            uniqueTag=self.unique_tag_base + u'_at_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

    def _schedule_event_at_end_of_interval(self):
        slot_len = self.settings.tsch_slotDuration * 1000  # convert to ms
        asn = self.engine.getAsn() + int(math.ceil(old_div(self.interval, slot_len)))

        def _callback():
            # doubling the interval
            #
            # Section 4.2:
            #   5.  When the interval I expires, Trickle doubles the interval
            #       length.  If this new interval length would be longer than
            #       the time specified by Imax, Trickle sets the interval
            #       length I to be the time specified by Imax.
            self.interval = self.interval * 2
            if self.max_interval < self.interval:
                self.interval = self.max_interval
                self.m = self.i_max
            self._start_next_interval()

        self.engine.scheduleAtAsn(
            asn=asn,
            cb=_callback,
            uniqueTag=self.unique_tag_base + u'_at_i',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)
