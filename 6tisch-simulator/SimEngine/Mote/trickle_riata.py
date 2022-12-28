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

class RiataTrickle(object):
    STATE_STOPPED = u'stopped'
    STATE_RUNNING = u'running'

    def __init__(self, i_min, i_max, k, callback, mote):
        assert isinstance(i_min, (int, int))
        assert isinstance(i_max, (int, int))
        assert isinstance(k, (int, int))
        assert callback is not None

        self.mote = mote

        # shorthand to singletons
        self.engine   = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log      = SimEngine.SimLog.SimLog().log

        # constants of this timer instance
        # min_interval is expected to given in milliseconds
        # max_interval is expected to be described as a number of doublings of the
        # minimum interval size
        self.min_interval = i_min
        self.max_interval = self.min_interval * pow(2, i_max)
        self.unique_tag_base = str(id(self))

        # variables
        self.counter = 0
        self.interval = 0
        self.user_callback = callback
        self.state = self.STATE_STOPPED

        self.alpha = self.settings.ql_learning_rate
        self.betha = self.settings.ql_discount_rate
        self.epsilon = self.settings.ql_epsilon

        self.i_max = i_max
        self.m = 0
        self.q_table = np.zeros([self.i_max + 1, 2])
        self.riatareset = np.zeros(self.i_max + 1)
        self.Ndio = np.zeros(self.i_max + 1)
        self.DIOtransmit = 0
        self.kmax = self.settings.k_max
        self.redundancy_constant = self.kmax
        self.current_action = -1
        self.t_start = 0
        self.t_end = 0
    
        self.pfree = 1
        self.poccupancy = 0
        self.t_pos = 0
        self.Nreset = 0
        self.preset = 0
        self.pstable = 1
        self.Nstates = 1
        self.DIOtransmit_log = 0
        self.DIOsurpress_log = 0
        self.Ncells = None
        self.is_dio_sent = False
        self.start_t_record = None
        self.end_t_record = None

    @property
    def is_running(self):
        return self.state == self.STATE_RUNNING

    def start(self, note=None):
        # Section 4.2:
        #   1.  When the algorithm starts execution, it sets I to a value in
        #       the range of [Imin, Imax] -- that is, greater than or equal to
        #       Imin and less than or equal to Imax.  The algorithm then begins
        #       the first interval.
        self.state = self.STATE_RUNNING
        self.m = 0
        self.interval = self.min_interval
        self._start_next_interval()

    def stop(self):
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_i')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_start_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_end_t')
        self.state = self.STATE_STOPPED

    def reset(self, note=None):
        # print(self.mote.id, f'reset {note}')
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

        self.Nreset += 1
        self.preset = self.Nreset / self.Nstates
        self.pstable = 1 - self.preset

        self.riatareset[self.m] += 1
        self.Ndio[self.m] = 0

        self.m = 0
        self.DIOtransmit = 0
        self.counter = 0
        self.interval = self.min_interval
        self._start_next_interval()

    def increment_counter(self):
        # this method is expected to be called when a "consistent" transmission
        # is heard.
        #
        # Section 4.2:
        #   3.  Whenever Trickle hears a transmission that is "consistent", it
        #       increments the counter c.
        self.counter += 1

    def calculate_k(self):
        total = 0
        for i in range(self.m + 1):
            total += self.Ndio[i]
        k = int(math.ceil(old_div(total, self.m + 1)))
        return k

    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self._schedule_event_at_t()
        self._schedule_event_at_end_of_interval()

    def _schedule_event_at_t(self):
        # select t in the range [I/2, I), where I == self.current_interval
        #
        # Section 4.2:
        #   2.  When an interval begins, Trickle resets c to 0 and sets t to a
        #       random point in the interval, taken from the range [I/2, I),
        #       that is, values greater than or equal to I/2 and less than I.
        #       The interval ends at I.
        slot_len = self.settings.tsch_slotDuration * 1000 # convert to ms

        I = old_div(self.interval, (self.m + 1 + self.riatareset[self.m]))
        self.t_start = self.DIOtransmit * I
        self.t_end = (self.DIOtransmit + 1)  * I
        self.t_start = int(math.ceil(self.t_start))
        self.t_end = int(math.ceil(self.t_end))
        t_range = self.t_end - self.t_start
        t = random.uniform(self.t_start, self.t_end)
        self.t_pos = round(t / self.interval, 1)

        l_e = slot_len * self.settings.tsch_slotframeLength
        self.Ncells = max(int(math.ceil(old_div(t_range, l_e))), 1)

        cur_asn = self.engine.getAsn()
        asn_start = cur_asn + int(math.ceil(old_div(self.t_start, slot_len)))
        asn_end = cur_asn + int(math.ceil(old_div(self.t_end, slot_len)))
        asn = cur_asn + int(math.ceil(old_div(t, slot_len)))

        if asn == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn = self.engine.getAsn() + 1

        if asn_start == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn_start = self.engine.getAsn() + 1

        if asn_end == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn_end = self.engine.getAsn() + 1

        def _callback():
            self.mote.tsch.set_is_dio_sent(False)
            self.is_dio_sent = False

            if random.uniform(0, 1) <= self.epsilon:
                # Explore action space
                if self.counter < self.redundancy_constant or self.redundancy_constant == 0:
                    #  Section 4.2:
                    #    4.  At time t, Trickle transmits if and only if the
                    #        counter c is less than the redundancy constant k.
                    self.is_dio_sent = True
                    self.user_callback()
                else:
                    # do nothing
                    pass
            else:
                # Exploit learned values
                action = np.argmax(self.q_table[self.m])

                if action == 1:
                    self.is_dio_sent = True
                    self.user_callback()
                else:
                    # do nothing
                    pass
        
            if self.is_dio_sent:
                self.current_action = 1
                self.DIOtransmit += 1
                self.DIOtransmit_log += 1
            else:
                self.current_action = 0
                self.DIOsurpress_log += 1

        def start_t():
            minimal_cell = self.mote.tsch.get_cell(0, 0, None, 0)
            self.start_t_record = None
            if minimal_cell:
                self.start_t_record = minimal_cell.all_ops

        def end_t():
            minimal_cell = self.mote.tsch.get_cell(0, 0, None, 0)
            self.end_t_record = None
            if minimal_cell:
                self.end_t_record = minimal_cell.all_ops

        self.engine.scheduleAtAsn(
            asn            = asn_start,
            cb             = start_t,
            uniqueTag      = self.unique_tag_base + u'_at_start_t',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)

        self.engine.scheduleAtAsn(
            asn            = asn_end,
            cb             = end_t,
            uniqueTag      = self.unique_tag_base + u'_at_end_t',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)

        self.engine.scheduleAtAsn(
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_t',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)

    def update_qtable(self):
        if self.current_action == 0:
            reward = 1 - self.riatareset[self.m]
        else:
            reward = self.riatareset[self.m]

        # clip m
        if self.i_max < (self.m + 1):
            next_m = self.m
        else:
            next_m = self.m + 1

        next_action = np.max(self.q_table[next_m])
        old_value = self.q_table[self.m][self.current_action]
        td_learning = (reward + self.betha * next_action) - old_value

        new_value = (1 - self.alpha) * old_value + self.alpha * td_learning
        self.q_table[self.m][self.current_action] = new_value

    def log_result(self):
        result = {
            'state': self.Nstates,
            'm': self.m,
            'pfree': self.pfree,
            'poccupancy': self.poccupancy,
            'DIOtransmit': self.DIOtransmit_log,
            'DIOsurpress': self.DIOsurpress_log,
            'Nreset': self.Nreset,
            'preset': self.preset,
            'pstable': self.pstable,
            't_pos': self.t_pos,
            'counter': self.counter,
            'k': self.redundancy_constant,
        }

        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )

    def _schedule_event_at_end_of_interval(self):
        slot_len = self.settings.tsch_slotDuration * 1000 # convert to ms
        asn = self.engine.getAsn() + int(math.ceil(old_div(self.interval, slot_len)))

        def _callback():
            used = None
            occ = None
            if self.end_t_record is not None and self.start_t_record is not None:
                dio_sent = int(self.mote.tsch.is_dio_sent) * int(self.is_dio_sent)
                used = max((self.end_t_record - self.start_t_record) - dio_sent, 0)
                occ = used / self.Ncells
                self.poccupancy = occ
                self.pfree = 1 - self.poccupancy

            self.update_qtable()
            self.log_result()

            self.mote.tsch.set_is_dio_sent(False)
            self.is_dio_sent = False
            # doubling the interval
            #
            # Section 4.2:
            #   5.  When the interval I expires, Trickle doubles the interval
            #       length.  If this new interval length would be longer than
            #       the time specified by Imax, Trickle sets the interval
            #       length I to be the time specified by Imax.
            if self.Ndio[self.m] == 0:
                self.redundancy_constant = self.kmax
            else:
                self.redundancy_constant = self.calculate_k()
            self.interval = self.interval * 2
            self.m += 1
            if self.max_interval < self.interval:
                self.interval = self.max_interval
                self.m = self.i_max
            self.Ndio[self.m] += self.redundancy_constant
            self.riatareset[self.m] = 0
            self._start_next_interval()

        self.engine.scheduleAtAsn(
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_i',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)
