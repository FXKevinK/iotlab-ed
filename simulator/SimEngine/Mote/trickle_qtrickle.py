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


class QTrickle(object):
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
        self.start_t_record = None
        self.end_t_record = None
        self.is_dio_sent = False
        self.Nstates = 0
        self.Ncells = 0
        self.Nreset = 1
        self.poccupancy = 1
        self.preset = 1
        self.pfree = 1 - self.poccupancy
        self.pstable = 1 - self.preset
        self.ptransmit = 1
        self.DIOsurpress = 0
        self.DIOtransmit = 0
        self.m = 0
        self.Nnbr = 0
        self.kmax = self.settings.k_max
        self.current_action = -1
        self.t_start = 0
        self.t_end = 0
        self.t = 0
        self.q_table = np.zeros([self.i_max + 1, 2]).tolist()
        self.alpha = self.settings.ql_learning_rate
        self.betha = self.settings.ql_discount_rate
        self.epsilon = self.settings.ql_epsilon
        self.used = 0
        self.is_explore = None
        self.average_reward = 0
        self.total_reward = 0
        self.listen_period = 0
        self.asn_t_start = None
        self.asn_t_end = None

        self.adaptive_epsilon = self.settings.ql_adaptive_epsilon
        if self.adaptive_epsilon:
            self.max_epsilon = self.settings.ql_adaptive_epsilon
            self.min_epsilon = self.settings.ql_adaptive_min_epsilon
            self.decay_rate = self.settings.ql_adaptive_decay_rate
            self.delta = (self.max_epsilon - self.min_epsilon) * \
                self.decay_rate
            self.epsilon_exploit = 0
            self.epsilon_explore = 0
            self.epsilon = self.max_epsilon

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
        self.asn_t_start = None
        self.asn_t_end = None


    def reset(self, note=None):
        if self.state == self.STATE_STOPPED:
            return

        type_ = ""
        if note == 1:
            type_ = 'start'
        elif note == 2:
            type_ = "new rank"
        elif note == 3:
            type_ = "receive DIS"
        elif note == 4:
            type_ = "infinite rank"
        elif note == 5:
            type_ = 'join rpl'
        elif note == 6:
            type_ = "parent packet"

        self.log(
            SimEngine.SimLog.LOG_TRICKLE_RESET,
            {
                "_mote_id":   self.mote.id,
                "reset_type": type_
            }
        )

        self.m = 0
        self.interval = self.min_interval
        self.Nreset += 1
        self._start_next_interval()

    def increment_counter(self):
        self.counter += 1

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

        self.counter = 0
        self.redundancy_constant = self.calculate_k()
        self._schedule_event_at_t_and_i()

    def _schedule_event_at_t_and_i(self):
        slot_duration_ms = self.settings.tsch_slotDuration * 1000  # convert to ms
        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength

        # Calculate T
        half_interval = old_div(self.interval, 2)
        self.t_start = half_interval * (self.ptransmit * self.pfree)
        self.t_end = half_interval + (self.pstable * half_interval)


        self.t = random.uniform(self.t_start, self.t_end)
        self.listen_period = self.t - self.t_start
        t_range = self.t_end - self.t_start
        self.Ncells = self.ceil_division(t_range, slotframe_duration_ms)
        self.Ncells = max(self.Ncells, 1)

        # asn = seconds / tsch_slotDuration (s) = ms / slot_duration_ms
        cur_asn = self.engine.getAsn()
        self.asn_t_start = cur_asn + \
            self.ceil_division(self.t_start, slot_duration_ms)
        asn_t = cur_asn + self.ceil_division(self.t, slot_duration_ms)
        self.asn_t_end = cur_asn + self.ceil_division(self.t_end, slot_duration_ms)
        asn_i = cur_asn + self.ceil_division(self.interval, slot_duration_ms)

        assert self.asn_t_start >= 0 and self.asn_t_end >= 0 and asn_t >= 0 and asn_i >= 0

        if cur_asn > self.asn_t_start or cur_asn > asn_t or cur_asn > self.asn_t_end or cur_asn > asn_i:
            print("\ncheck")
            print(self.mote.id, ":", "t_start", self.t_start, "t_end", self.t_end,
                  "t", self.t, "t_range", t_range, "interval", self.interval)
            print(self.mote.id, ":", "cur_asn", cur_asn, "asn_start",
                  self.asn_t_start, "asn_t", asn_t, "asn_end", self.asn_t_end, "asn_i", asn_i)
            print("preset", self.preset, "pstable:", self.pstable, "ptransmit",
                  self.ptransmit, "pfree", self.pfree, "Ncells", self.Ncells)

        def t_callback():
            self.is_dio_sent = False
            self.is_explore = random.uniform(0, 1) <= self.epsilon
            if self.is_explore:
                # Explore action space
                if self.counter < self.redundancy_constant or self.redundancy_constant == 0:
                    self.is_dio_sent = True
                    self.user_callback()
            else:
                # Exploit learned values
                action = np.argmax(self.q_table[self.m])
                if action == 1:
                    self.is_dio_sent = True
                    self.user_callback()

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
            asn=self.correctASN(self.asn_t_start),
            cb=start_t,
            uniqueTag=self.unique_tag_base + u'_at_start_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        if self.t_end < self.interval:
            self.engine.scheduleAtAsn(
                asn=self.correctASN(self.asn_t_end),
                cb=end_t,
                uniqueTag=self.unique_tag_base + u'_at_end_t',
                intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        # ========================

        def i_callback():
            if self.is_dio_sent:
                self.DIOtransmit += 1
                self.current_action = 1
            else:
                self.DIOsurpress += 1
                self.current_action = 0

            self.calculate_pfree()
            self.calculate_ptransmit()

            self.update_qtable()
            self.total_reward += self.pfree
            self.average_reward = self.total_reward / self.Nstates
            if self.adaptive_epsilon:
                self.calculate_epsilon()

            # ===== Start new interval
            # doubling the interval
            #
            # Section 4.2:
            #   5.  When the interval I expires, Trickle doubles the interval
            #       length.  If this new interval length would be longer than
            #       the time specified by Imax, Trickle sets the interval
            #       length I to be the time specified by Imax.
            self.interval = self.interval * 2
            self.m += 1
            if self.max_interval < self.interval:
                self.interval = self.max_interval
                self.m = self.i_max
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
        assert 0 <= self.preset and self.preset <= 1
        self.pstable = 1 - self.preset

    def calculate_ptransmit(self):
        self.ptransmit = self.DIOtransmit / self.Nstates
        assert 0 <= self.ptransmit and self.ptransmit <= 1

    def calculate_pfree(self):
        if self.end_t_record is not None and self.start_t_record is not None:
            self.used = self.end_t_record - self.start_t_record
            if self.Ncells < self.used: self.Ncells = self.used
            occ = self.used / self.Ncells
            self.poccupancy = occ
            assert 0 <= self.poccupancy and self.poccupancy <= 1
            self.pfree = 1 - self.poccupancy

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
            'm': self.m,
            'DIOtransmit': self.DIOtransmit,
            'DIOsurpress': self.DIOsurpress,
            'Nreset': self.Nreset,
            'pfree': self.pfree,
            'poccupancy': self.poccupancy,
            'preset': self.preset,
            'pstable': self.pstable,
            'counter': self.counter,
            'k': self.redundancy_constant,
            'used': self.used,
            'Ncells': self.Ncells,
            'epsilon': self.epsilon,
            "average_reward": self.average_reward,
            'listen_period': self.listen_period,
            't_start': self.t_start,
            't': self.t,
            't_end': self.t_end,
            'interval': self.interval,
            'nbr': self.Nnbr,
        }

        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )

    def update_qtable(self):
        reward = self.pfree

        # clip m
        next_m = self.m + 1
        if self.i_max < next_m:
            next_m = self.i_max

        next_action_value = np.max(self.q_table[next_m])
        old_value = self.q_table[self.m][self.current_action]
        td_learning = (reward + self.betha * next_action_value) - old_value

        new_value = (1 - self.alpha) * old_value + (self.alpha * td_learning)
        self.q_table[self.m][self.current_action] = new_value

    def calculate_k(self):
        self.Nnbr = self.kmax
        if hasattr(self.mote.rpl.of, 'neighbors'):
            self.Nnbr = len(self.mote.rpl.of.neighbors)

        k = 1 + math.ceil(min(self.Nnbr, self.kmax - 1) * self.preset)
        return k

    def calculate_epsilon(self):
        new_epsilon = self.epsilon

        if self.Nstates > 1:
            if self.pfree > self.average_reward:
                # towards exploit
                new_epsilon -= self.delta
                self.epsilon_exploit += 1
            else:
                # towards explore
                new_epsilon += self.delta
                self.epsilon_explore += 1

        new_epsilon = max(new_epsilon, self.min_epsilon)
        new_epsilon = min(new_epsilon, self.max_epsilon)
        self.epsilon = new_epsilon