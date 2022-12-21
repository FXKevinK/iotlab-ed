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

import numpy as np
import random

# DEFAULT_DIO_INTERVAL_MIN = 14
# DEFAULT_DIO_INTERVAL_DOUBLINGS = 9
# DEFAULT_DIO_REDUNDANCY_CONSTANT = 3

class RiataTrickle(object):
    STATE_STOPPED = u'stopped'
    STATE_RUNNING = u'running'

    def __init__(self, i_min, i_max, k, callback, mote):
        assert isinstance(i_min, (int, int))
        assert isinstance(i_max, (int, int))
        assert isinstance(k, (int, int))
        assert callback is not None

        # shorthand to singletons
        self.engine   = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.mote = mote

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

        # =======================
        
        self.alpha = 0.5
        self.gamma = 0.5
        self.epsilon = 0.5
        self.kmax = 10

        self.i_max = i_max
        self.m = -1
        self.q_table = np.zeros([self.i_max, 2])
        self.prev_psuccess = 1

        self.Nreset = np.zeros(self.i_max)
        self.Ndio = np.zeros(self.i_max)

        self.DIOtransmit = 0
        self.Nstates = 0
        self.current_action = -1
        self.t_start = 0
        self.t_end = 0

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
        self.interval = self.min_interval
        # self.interval = random.randint(self.min_interval, self.max_interval)
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

        self.Nreset[self.m] += 1
        if self.min_interval < self.interval:
            self.interval = self.min_interval
            self.m = -1
            self.Ndio[self.m+1] = 0
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
        self.Ndio[self.m] += 1
    
    def calculate_k(self):
        if self.Nstates == 0:
            return self.kmax

        total = 0
        for i in range(0, self.m+1):
            total += self.Ndio[i]
        k = old_div(total, self.m+1)

        return k

    def calculate_interval_t(self):
        # t = old_div((1 + random.random()) * self.interval, 2)
        # t_start = old_div(self.interval, 2)
        # t_end = self.interval

        I = old_div(self.interval, (self.m + 1 + self.Nreset[self.m]))
        self.t_start = self.DIOtransmit * I
        self.t_end = (self.DIOtransmit + 1)  * I
        t = random.randint(self.t_start, self.t_end)
        return t

    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self.counter = 0

        self.m += 1
        if self.i_max < self.m:
            self.m = self.i_max
        assert self.m > -1 and self.m <= self.i_max
        
        self.Nreset[self.m] = 0
        self.Ndio[self.m] = 0
        self.Nstates += 1

        self.redundancy_constant = self.calculate_k()
        t = self.calculate_interval_t()

        self._schedule_event_at_t(t)
        self._schedule_event_at_end_of_interval()

    def _schedule_event_at_t(self, t):
        # select t in the range [I/2, I), where I == self.current_interval
        #
        # Section 4.2:
        #   2.  When an interval begins, Trickle resets c to 0 and sets t to a
        #       random point in the interval, taken from the range [I/2, I),
        #       that is, values greater than or equal to I/2 and less than I.
        #       The interval ends at I.
        slot_len = self.settings.tsch_slotDuration * 1000 # convert to ms
        asn = self.engine.getAsn() + int(math.ceil(old_div(t, slot_len)))
        if asn == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn = self.engine.getAsn() + 1

        def _callback():

            if random.uniform(0, 1) <= self.epsilon:
                # Explore action space
                if self.counter < self.redundancy_constant:
                    #  Section 4.2:
                    #    4.  At time t, Trickle transmits if and only if the
                    #        counter c is less than the redundancy constant k.
                    self.user_callback()
                    self.current_action = 1
                    self.DIOtransmit += 1
                else:
                    # do nothing
                    self.current_action = 0

            else:
                # Exploit learned values
                action = np.argmax(self.q_table[self.m])

                if action == 1:
                    self.user_callback()
                    self.current_action = 1
                    self.DIOtransmit += 1
                else:
                    # do nothing
                    self.current_action = 0

        self.engine.scheduleAtAsn(
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_t',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)

    def update_qtable(self):
        # next m
        if self.i_max < (self.m + 1):
            next_m = self.m
        else:
            next_m = self.m + 1

        if self.current_action == 0:
            reward = 1 - self.Nreset[self.m]
        else:
            reward = self.Nreset[self.m]

        next_max = np.max(self.q_table[next_m])
        old_value = self.q_table[self.m][self.current_action]
        td_learning = (reward + self.gamma * next_max) - old_value

        new_value = (1 - self.alpha) * old_value + self.alpha * td_learning
        self.q_table[self.m][self.current_action] = new_value
        
        self.prev_psuccess = self.psuccess[self.m]

    def _schedule_event_at_end_of_interval(self):
        slot_len = self.settings.tsch_slotDuration * 1000 # convert to ms
        asn = self.engine.getAsn() + int(math.ceil(old_div(self.interval, slot_len)))

        self.update_qtable()

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
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_i',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)
