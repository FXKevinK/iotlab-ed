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


class TrickleTimer(object):
    STATE_STOPPED = u'stopped'
    STATE_RUNNING = u'running'

    def __init__(self, callback, mote):
        assert callback is not None

        # shorthand to singletons
        self.engine = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log = SimEngine.SimLog.SimLog().log

        self.mote = mote
        i_min = self.settings.dio_interval_min_s * 1000  # to ms
        i_max = self.settings.dio_interval_doublings
        self.redundancy_constant = self.settings.k_max
        self.kmax = self.settings.k_max
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
        self.Nreset_prev = 1
        self.pbusy = 1
        self.preset = 1
        self.pfree = 1 - self.pbusy
        self.pstable = 1 - self.preset
        self.ptransmit = 1
        self.DIOsurpress = 0
        self.DIOtransmit = 0
        self.used = 0
        self.listen_period = 0
        self.t_range = None
        self.Ncells_all = 0
        self.ops_all = 0
        self.pfree_all = 0
        self.used_all = 0
        self.asn_t_start = None
        self.asn_t_end = None
        self.qul = 0
        self.Nnbr = 0
        self.psent = 0
        self.pfailed = 1

        if getattr(self.settings, "algo_use_ql", False):
            self.alpha = self.settings.ql_learning_rate
            self.betha = self.settings.ql_discount_rate
            self.epsilon = self.settings.ql_epsilon
            self.classes = ['low', 'medium', 'high']
            self.num_class = len(self.classes)
            self.ql_table = np.zeros([self.num_class, 2]).tolist()
            self.reward = 0
            self.average_reward = 0
            self.total_reward = 0
            self.current_action = 0
            self.pbusy_prev = self.pbusy
            self.psent_prev = self.psent
            self.s1 = self.psent_prev
            self.n_s1 = self.psent
            self.is_explore = False

            if getattr(self.settings, "algo_adaptive_epsilon", False):
                self.max_epsilon = getattr(self.settings, "ql_adaptive_max_epsilon", 1)
                self.min_epsilon = getattr(self.settings, "ql_adaptive_min_epsilon", 0.01)
                self.decay_rate = self.settings.ql_adaptive_decay_rate
                self.delta = (self.max_epsilon - self.min_epsilon) * self.decay_rate
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

        self.Nreset += 1
        self.interval = self.min_interval
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
        self.Nnbr = len(self.mote.rpl.of.neighbors) if hasattr(self.mote.rpl.of, 'neighbors') else 0

        if getattr(self.settings, "algo_auto_k", False):
            self.redundancy_constant = self.calculate_k()
        self._schedule_event_at_t_and_i()

        self.log_result()
        self.Nreset_prev = self.Nreset
        self.pbusy_prev = self.pbusy
        self.psent_prev = self.psent
        self.counter = 0

    def _schedule_event_at_t_and_i(self):
        slot_duration_ms = self.settings.tsch_slotDuration * 1000  # convert to ms
        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength

        # Calculate T
        half_interval = old_div(self.interval, 2)

        self.t_start = half_interval
        self.t_end = self.interval
        if getattr(self.settings, "algo_auto_t", False):
            self.t_start = half_interval * (self.ptransmit * self.pfree)
            self.t_end = half_interval + (self.pstable * half_interval)

        self.t = random.uniform(self.t_start, self.t_end)
        assert self.t_start <= self.t_end <= self.interval
        assert self.t_start <= self.t <= self.t_end

        self.listen_period = self.t - self.t_start
        self.t_range = self.t_end - self.t_start
        self.Ncells = self.ceil_division(self.t_range, slotframe_duration_ms)

        self.ops_all = self.getOpsMC()
        self.Ncells_all = self.ceil_division(
            self.interval, slotframe_duration_ms)

        # asn = seconds / tsch_slotDuration (s) = ms / slot_duration_ms
        cur_asn = self.engine.getAsn()
        self.asn_t_start = cur_asn + \
            self.ceil_division(self.t_start, slot_duration_ms)
        asn_t = cur_asn + self.ceil_division(self.t, slot_duration_ms)
        self.asn_t_end = cur_asn + \
            self.ceil_division(self.t_end, slot_duration_ms)
        asn_i = cur_asn + self.ceil_division(self.interval, slot_duration_ms)

        assert self.asn_t_start >= 0 and self.asn_t_end >= 0 and asn_t >= 0 and asn_i >= 0

        def t_callback():
            self.is_dio_sent = False
            self.is_explore = random.uniform(
                0, 1) < self.epsilon if getattr(self.settings, "algo_use_ql", False) else 1

            if self.is_explore:
                if self.counter < self.redundancy_constant:
                    self.is_dio_sent = True
                    self.user_callback()
            else:
                # Exploit learned values
                s1 = self.prob_to_class(self.psent_prev)
                action = np.argmax(self.ql_table[s1])
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
            self.calculate_psent()
            # self.calculate_pqu()
            # self.calculate_pfree_all()

            if getattr(self.settings, "algo_use_ql", False):
                self.update_qtable()
            
            if getattr(self.settings, "algo_adaptive_epsilon", False):
                self.total_reward += self.reward
                self.average_reward = self.total_reward / self.Nstates
                self.calculate_epsilon()

            self.interval = self.interval * 2
            self.interval = max(min(self.max_interval, self.interval), self.min_interval)
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

    def calculate_psent(self):
        self.pfailed = self.mote.rpl.get_failed_dio(True, True)
        self.psent = 1 - self.pfailed
        assert 0 <= self.psent <= 1

    def calculate_pqu(self):
        self.pqu = self.mote.tsch.get_queue_usage()
        assert 0 <= self.pqu and self.pqu <= 1

    def calculate_pfree(self):
        if (
            self.end_t_record is not None and
            self.start_t_record is not None and
            self.Ncells
        ):
            self.used = self.end_t_record - self.start_t_record
            if self.Ncells < self.used:
                self.Ncells = self.used
            occ = self.used / self.Ncells
            self.pbusy = occ
            assert 0 <= self.pbusy <= 1
            self.pfree = 1 - self.pbusy

    def calculate_pfree_all(self):
        curr_ = self.getOpsMC()
        if (
            self.ops_all is not None and
            curr_ is not None and
            self.Ncells_all
        ):
            self.used_all = curr_ - self.ops_all
            if self.Ncells_all < self.used_all:
                self.Ncells_all = self.used_all
            occ_ = self.used_all / self.Ncells_all
            pbusy_ = occ_
            assert 0 <= pbusy_ <= 1
            self.pfree_all = 1 - pbusy_

    def getOpsMC(self):
        minimal_cell = self.mote.tsch.get_minimal_cell()
        if minimal_cell:
            return minimal_cell.all_ops
        return None

    def correctASN(self, asn_):
        cur = self.engine.getAsn()
        if asn_ == cur:
            asn_ = cur + 1
        return asn_

    def ceil_division(self, a, b):
        return int(math.ceil(old_div(a, b)))

    def log_result(self):
        result = {
            'state': self.Nstates,
            'pbusy': self.pbusy,
            'pfree': self.pfree,
            'ptransmit': self.ptransmit,
            'psent': self.psent,
            'pfailed': self.pfailed,
            'nbr': self.Nnbr,
            # 'pfree_all': self.pfree_all,
            'Nreset': self.Nreset,
            # 'Nreset_prev': self.Nreset_prev,
            'is_prev_reset': self.is_prev_reset(),
            'preset': self.preset,
            'pstable': self.pstable,
            'counter': self.counter,
            'k': self.redundancy_constant,
            't_range': self.t_range,
            'listen_period': self.listen_period,
            't': self.t,
            'interval': self.interval,
            't_pos': self.t / self.interval,
            # 'used': self.used,
            # 'Ncells': self.Ncells,
            # 'Ncells_all': self.Ncells_all,
            # 'used_all': self.used_all
        }
        
        if getattr(self.settings, "algo_use_ql", False):
            c1 = self.classes[self.s1] if self.s1 is not None else None
            n_c1 = self.classes[self.n_s1] if self.s1 is not None else None
            result['epsilon'] = self.epsilon
            result['s1_class'] = c1
            result['n_s1_class'] = n_c1

        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )

    def prob_to_class(self, prob):
        assert 0 <= prob <= 1
        limit_per_class = 1 / self.num_class
        class_ = prob / limit_per_class
        class_ = int(np.ceil(class_))
        if class_ == 0:
            class_ = 1
        return class_ - 1

    def is_prev_reset(self):
        diff = self.Nreset - self.Nreset_prev
        return diff > 0

    def update_qtable(self):
        self.reward = self.pfree

        self.s1 = self.prob_to_class(self.psent_prev)
        old_value = self.ql_table[self.s1][self.current_action]

        self.n_s1 = self.prob_to_class(self.psent)
        next_q = self.ql_table[self.n_s1]

        td = (self.reward + self.betha * np.max(next_q)) - old_value
        new_value = (1 - self.alpha) * old_value + self.alpha * td
        self.ql_table[self.s1][self.current_action] = new_value

    def calculate_k(self):
        k = 1 + math.ceil(min(self.Nnbr, self.kmax - 1) * self.preset)
        return k
    def calculate_epsilon(self):
        new_epsilon = self.epsilon

        if self.Nstates > 1:
            if self.pfree > self.average_reward:
                # towards exploit
                new_epsilon -= self.delta
            else:
                # towards explore
                new_epsilon += self.delta

        new_epsilon = max(new_epsilon, self.min_epsilon)
        new_epsilon = min(new_epsilon, self.max_epsilon)
        self.epsilon = new_epsilon
