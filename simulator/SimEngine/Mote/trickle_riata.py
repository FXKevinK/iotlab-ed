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
import numpy as np
import SimEngine
from . import MoteDefines as d


class RiataTrickle(object):
    STATE_STOPPED = u'stopped'
    STATE_RUNNING = u'running'

    def __init__(self, callback, mote):
        assert callback is not None

        # shorthand to singletons
        self.engine = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log = SimEngine.SimLog.SimLog().log

        self.mote = mote
        i_min = self.settings.dio_interval_min_s * 1000 # to ms
        i_max = self.settings.dio_interval_doublings
        self.redundancy_constant = self.settings.k_max
        self.i_max = i_max
        self.is_explore = None
        self.used = 0
        self.average_reward = 0
        self.total_reward = 0
        self.listen_period = 0

        # constants of this timer instance
        # min_interval is expected to given in milliseconds
        # max_interval is expected to be described as a number of doublings of the
        # minimum interval size
        self.min_interval = i_min
        self.max_interval = self.min_interval * pow(2, i_max)
        self.unique_tag_base = str(id(self))

        # variables
        self.interval = 0
        self.user_callback = callback
        self.state = self.STATE_STOPPED
        self.start_t_record = None
        self.end_t_record = None
        self.is_dio_sent = False
        self.Nstates = 0
        self.Ncells = 0
        self.Nreset = 1
        self.pbusy = 1
        self.preset = 1
        self.pfree = 1 - self.pbusy
        self.pstable = 1 - self.preset
        self.ptransmit = 0
        self.DIOsurpress = 0
        self.DIOtransmit = 0
        self.m_riata = 1 # m as interval states
        self.DIOsent = 0
        self.kmax = self.settings.k_max
        self.t_start = 0
        self.t_end = 0
        self.t = 0
        self.ql_table = np.zeros([2, 2]).tolist()
        self.alpha = self.settings.ql_learning_rate
        self.betha = self.settings.ql_discount_rate
        self.epsilon = self.settings.ql_epsilon
        self.inconc = {self.m_riata: 0}
        self.Ndio = {}
        self.counter = {self.m_riata: 0}
        self.prev_state = 0
        self.average_reward = 0
        self.total_reward = 0
        self.listen_period = 0

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
        self.m_riata = 1
        self.interval = self.min_interval
        self._start_next_interval()

    def stop(self):
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_i')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_start_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_end_t')
        self.state = self.STATE_STOPPED

    def reset(self, note=None):
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
        self.interval = self.min_interval
        self.DIOsent = 0
        self.m_riata = 1
        self.counter[self.m_riata] = 0
        self.Ndio[self.m_riata] = 0

        # populate
        if self.m_riata not in self.inconc: self.inconc[self.m_riata] = 0
        self.inconc[self.m_riata] += 1
        
        self.Nreset += 1
        self._start_next_interval()

    def increment_counter(self):
        # populate
        if self.m_riata not in self.counter: self.counter[self.m_riata] = 0
        self.counter[self.m_riata] += 1

    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_i')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_start_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_end_t')

        self.Nstates += 1
        self.calculate_preset()
        self.log_result()

        self._schedule_event_at_t_and_i()

    def _schedule_event_at_t_and_i(self):
        # select t in the range [I/2, I), where I == self.current_interval
        #
        # Section 4.2:
        #   2.  When an interval begins, Trickle resets c to 0 and sets t to a
        #       random point in the interval, taken from the range [I/2, I),
        #       that is, values greater than or equal to I/2 and less than I.
        #       The interval ends at I.
        slot_duration_ms = self.settings.tsch_slotDuration * 1000  # convert to ms
        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength

        # populate
        if self.m_riata not in self.inconc: self.inconc[self.m_riata] = 0

        I_ = old_div(self.interval, (self.m_riata + self.inconc[self.m_riata]))
        self.t_start = self.DIOsent * I_
        self.t_end = (self.DIOsent + 1) * I_
        self.t_start = int(math.ceil(self.t_start))
        self.t_end = int(math.ceil(self.t_end))

        self.t = random.uniform(self.t_start, self.t_end)
        self.listen_period = self.t - self.t_start
        t_range = self.t_end - self.t_start
        self.Ncells = self.ceil_division(t_range, slotframe_duration_ms)
        self.Ncells = max(self.Ncells, 1)

        # asn = seconds / tsch_slotDuration (s) = ms / slot_duration_ms
        cur_asn = self.engine.getAsn()
        asn_start = cur_asn + \
            self.ceil_division(self.t_start, slot_duration_ms)
        asn_t = cur_asn + self.ceil_division(self.t, slot_duration_ms)
        asn_end = cur_asn + self.ceil_division(self.t_end, slot_duration_ms)
        asn_i = cur_asn + self.ceil_division(self.interval, slot_duration_ms)

        if cur_asn > asn_start or cur_asn > asn_t or cur_asn > asn_end or cur_asn > asn_i:
            print("\ncheck")
            print(self.mote.id, ":", "t_start", self.t_start, "t_end", self.t_end,
                  "t", self.t, "t_range", t_range, "interval", self.interval)
            print(self.mote.id, ":", "cur_asn", cur_asn, "asn_start",
                  asn_start, "asn_t", asn_t, "asn_end", asn_end, "asn_i", asn_i)
            print("preset", self.preset, "pstable:", self.pstable, "ptransmit",
                  self.ptransmit, "pfree", self.pfree, "Ncells", self.Ncells)

        def t_callback():
            self.is_dio_sent = False
            self.is_explore = random.uniform(0, 1) < self.epsilon
            if self.is_explore:
                # populate
                if self.m_riata not in self.counter: self.counter[self.m_riata] = 0

                # Explore action space
                if self.counter[self.m_riata] < self.redundancy_constant or self.redundancy_constant == 0:
                    self.is_dio_sent = True
                    self.user_callback()
                else:
                    pass
            else:
                # Exploit learned values
                change = np.argmax(self.ql_table[self.prev_state])
                if self.prev_state:
                    self.is_dio_sent = False if change else True
                else:
                    self.is_dio_sent = True if change else False 

                if self.is_dio_sent:
                    self.user_callback()

            self.prev_state = self.is_dio_sent

        def start_t():
            self.start_t_record = self.getOpsMC()

        def end_t():
            self.end_t_record = self.getOpsMC()

        self.engine.scheduleAtAsn(
            asn=self.correctASN(asn_t),
            cb=t_callback,
            uniqueTag=self.unique_tag_base + u'_at_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        self.engine.scheduleAtAsn(
            asn=self.correctASN(asn_start),
            cb=start_t,
            uniqueTag=self.unique_tag_base + u'_at_start_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        if self.t_end < self.interval:
            asn_end = cur_asn + int(math.ceil(old_div(self.t_end, slot_duration_ms)))
            if asn_end == self.engine.getAsn():
                # schedule the event at the next ASN since we cannot schedule it at
                # the current ASN
                asn_end = self.engine.getAsn() + 1

            self.engine.scheduleAtAsn(
                asn=self.correctASN(asn_end),
                cb=end_t,
                uniqueTag=self.unique_tag_base + u'_at_end_t',
                intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        # ========================

        def i_callback():
            if self.is_dio_sent:
                self.DIOsent += 1
                self.DIOtransmit += 1
            else:
                self.DIOsurpress += 1

            self.calculate_pfree()
            self.calculate_ptransmit()

            self.update_qtable()
            self.total_reward += self.pfree
            self.average_reward = self.total_reward / self.Nstates


            # ===== Start new interval

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

            # populate
            if self.m_riata not in self.Ndio: self.Ndio[self.m_riata] = 0

            if self.Ndio[self.m_riata] == 0:
                self.redundancy_constant = self.kmax
            else:
                self.redundancy_constant = self.calculate_k()

            self.m_riata += 1

            # populate
            if self.m_riata not in self.Ndio: self.Ndio[self.m_riata] = 0
            self.Ndio[self.m_riata] += self.redundancy_constant
            self.inconc[self.m_riata] = 0
            self._start_next_interval()

        def end_t_i_callback():
            end_t()
            i_callback()

        self.engine.scheduleAtAsn(
            asn=self.correctASN(asn_i),
            cb=i_callback if self.t_end < self.interval else end_t_i_callback,
            uniqueTag=self.unique_tag_base + u'_at_i',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

    def calculate_preset(self):
        self.preset = self.Nreset / self.Nstates
        assert 0 <= self.preset <= 1
        self.pstable = 1 - self.preset

    def calculate_ptransmit(self):
        self.ptransmit = self.DIOtransmit / self.Nstates
        assert 0 <= self.ptransmit <= 1

    def calculate_pfree(self):
        if self.end_t_record is not None and self.start_t_record is not None:
            self.used = self.end_t_record - self.start_t_record
            if self.Ncells < self.used: self.Ncells = self.used
            occ = self.used / self.Ncells
            self.pbusy = occ
            assert 0 <= self.pbusy <= 1
            self.pfree = 1 - self.pbusy

    def getOpsMC(self):
        minimal_cell = self.mote.tsch.get_minimal_cell()
        if minimal_cell: return minimal_cell.all_ops
        return None

    def correctASN(self, asn_):
        cur = self.engine.getAsn()
        if asn_ == cur: asn_ = cur + 1
        return asn_

    def ceil_division(self, a, b):
        return int(math.ceil(old_div(a, b)))

    def log_result(self):
        result = {
            'state': self.Nstates,
            'm': self.m_riata,
            'pfree': self.pfree,
            'pbusy': self.pbusy,
            'DIOtransmit': self.DIOtransmit,
            'DIOsurpress': self.DIOsurpress,
            'Nreset': self.Nreset,
            'preset': self.preset,
            'pstable': self.pstable,
            'k': self.redundancy_constant,
            'listen_period': self.listen_period,
            'used': self.used,
            'Ncells': self.Ncells,
            'is_explore': self.is_explore,
            "average_reward": self.average_reward,
        }

        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )

    def update_qtable(self):
        if self.m_riata == 1:
            return

        prev_inconc =  self.inconc[self.m_riata - 1]
        current_state = self.is_dio_sent
        next_state = current_state

        change = 0 # no change
        if self.is_dio_sent:
            if prev_inconc:
                reward = 1
            else:
                reward = 0
                change = 1
        else:
            if prev_inconc:
                reward = -1
                change = 1
            else:
                reward = 1
        
        if change:
            next_state = not next_state

        next_action_value = np.max(self.ql_table[next_state])
        old_value = self.ql_table[current_state][change]
        td_learning = (reward + self.betha * next_action_value) - old_value

        new_value = (1 - self.alpha) * old_value + self.alpha * td_learning
        self.ql_table[current_state][change] = new_value

    def calculate_k(self):
        total = 0
        for i in range(1, self.m_riata+1):
            total += self.Ndio[i]
        k = int(math.ceil(old_div(total, self.m_riata)))
        return k
