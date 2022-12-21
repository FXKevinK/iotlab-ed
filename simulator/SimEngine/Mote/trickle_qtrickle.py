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

class QTrickle(object):
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
        self.log      = SimEngine.SimLog.SimLog().log

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

        self.mote = mote

        # =======================
        
        self.alpha = self.settings.ql_learning_rate
        self.betha = self.settings.ql_discount_rate
        self.epsilon = self.settings.ql_epsilon

        self.i_max = i_max
        self.m = -1
        self.q_table = np.zeros([self.i_max, 2])
        self.psuccess = np.zeros(self.i_max)
        self.pcollision = np.zeros(self.i_max)
        self.Ncell = np.zeros(self.i_max)
        self.num_collision_busy = np.zeros(self.i_max)
        self.prev_psuccess = 1

        self.Nreset = 0
        self.DIOtransmit = 0
        self.DIOtransmit_collision = 0
        self.DIOtransmit_collision_prob = 0
        self.Nstates = 0
        self.preset = 0
        self.pstable = 0
        self.Nnbr = 0
        self.kmax = 10
        self.ptransmit = 0
        self.current_action = -1
        self.ptransmit_collision = 0
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
            self.m = -1
            self.Nreset += 1
            self.calculate_reset_stable_prob()
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

    def calculate_reset_stable_prob(self):
        self.preset = self.Nreset / self.Nstates
        self.pstable = 1 - self.preset
    
    def calculate_k(self):
        a = len(self.mote.rpl.getNeighbors())
        b = len(self.mote.rpl.neighbors)
        print('neighbors', a, b)

        self.Nnbr = 3
        k = 1 + math.ceil( min(self.Nnbr, self.kmax - 1) * self.preset)
        return k

    # TODO DZAKY increase collision
    def increment_dio_collision(self):
        self.DIOtransmit_collision += 1
        
    def calculate_dio_transmit_collision(self):
        self.DIOtransmit_collision_prob = self.DIOtransmit_collision / self.DIOtransmit

    def calculate_ptransmit(self):
        self.ptransmit = self.DIOtransmit / self.Nstates
        self.ptransmit_collision = self.DIOtransmit_collision / self.DIOtransmit

    def calculate_current_collision_success(self):
        candidate_cells = self.mote.tsch.slotframes[0].get_cells_at_asn(1)
        cell, packet = self.mote.tsch._select_active_cell(candidate_cells)

        slotframe_len = self.settings.tsch_slotframeLength * self.settings.tsch_slotDuration * 1000 # convert to ms
        self.Ncell[self.m] = int(math.ceil(old_div((self.t_end-self.t_start), slotframe_len)))
        
        # TODO to get collision
        self.num_collision_busy[self.m] = 0

        assert self.num_collision_busy[self.m] <= self.Ncell[self.m]
        self.pcollision[self.m] = self.num_collision_busy[self.m] / self.Ncell[self.m]
        self.psuccess[self.m] =  1 - self.pcollision[self.m]


    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self.counter = 0
        self.redundancy_constant = self.calculate_k()
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

        # # Calculate T
        half_interval = old_div(self.interval, 2)
        self.t_start = half_interval * (self.ptransmit * self.prev_psuccess)
        self.t_end = half_interval + (self.pstable * half_interval)
        t = random.randint(self.t_start, self.t_end)

        asn = self.engine.getAsn() + int(math.ceil(old_div(t, slot_len)))
        if asn == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn = self.engine.getAsn() + 1

        def _transmit():
            self.calculate_ptransmit()
            self.current_action = 1
            self.DIOtransmit += 1

        def _callback():
            if random.uniform(0, 1) <= self.epsilon:
                # Explore action space
                if self.counter < self.redundancy_constant:
                    #  Section 4.2:
                    #    4.  At time t, Trickle transmits if and only if the
                    #        counter c is less than the redundancy constant k.
                    self.user_callback()
                    _transmit()
                else:
                    # do nothing
                    self.current_action = 0

            else:
                # Exploit learned values
                action = np.argmax(self.q_table[self.m])

                if action == 1:
                    self.user_callback()
                    _transmit()
                else:
                    # do nothing
                    self.current_action = 0

        # log
        self.log(
            SimEngine.SimLog.LOG_DEBUG_ASN,
            {
                u'_mote_id':        self.mote.id,
                u'position':        2,
                u'asn':             asn,
            }
        )
        
        self.engine.scheduleAtAsn(
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_t',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)

    def update_qtable(self):
        reward = self.psuccess[self.m]
        # clip m
        if self.i_max < (self.m + 1):
            next_m = self.m
        else:
            next_m = self.m + 1

        next_max = np.max(self.q_table[next_m])
        old_value = self.q_table[self.m][self.current_action]
        td_learning = (reward + self.betha * next_max) - old_value

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
            self.m += 1
            self.Nstates += 1
            if self.max_interval < self.interval:
                self.interval = self.max_interval
                self.m = self.i_max
            self._start_next_interval()
            self.calculate_current_collision_success()

        self.engine.scheduleAtAsn(
            asn            = asn,
            cb             = _callback,
            uniqueTag      = self.unique_tag_base + u'_at_i',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS)
