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

    def __init__(self, callback, mote):
        assert callback is not None

        # shorthand to singletons
        self.engine = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log = SimEngine.SimLog.SimLog().log

        self.mote = mote

        # calculate slotframe duration
        slot_duration_ms = self.settings.tsch_slotDuration * 1000  # convert to ms
        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength

        i_min = self.settings.dio_interval_min_s * slotframe_duration_ms  # to ms
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
        self.interval = 0
        self.user_callback = callback
        self.state = self.STATE_STOPPED
        self.start_t_record = None
        self.end_t_record = None
        self.is_dio_sent = False
        self.Nstates = 0
        self.Ncells = 0
        self.DIOsurpress = 0
        self.DIOtransmit = 0
        self.used = 0
        self.listen_period = 0
        self.Nnbr = 0
        self.t = 0
        self.t_range = None
        self.asn_t_start = None
        self.asn_t_end = None
        self.qul = 0
        self.counter = 0

        # self.Nreset = 1
        # self.pbusy = 1
        # self.preset = 1
        # self.pfree = 1 - self.pbusy
        # self.pstable = 1 - self.preset
        # self.ptransmit = 1
        # self.pfailed = 1

        self.Nreset = 0
        self.pbusy = 0 # None
        self.pfree = 0 # None
        self.preset = 0 # None
        self.pstable = 0 #None
        self.ptransmit = 0 # None
        self.pfailed = 0 # None
        self.psent = 0 # None
        self.pqu = 0

        # for acpb
        self.transmitted = 0
        self.suppressed = 0
        self.flag = None
        self.m = 0

    @property
    def is_running(self):
        return self.state == self.STATE_RUNNING

    def start(self, note=None):
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
        self.calculate_preset()
        self.log_result(is_reset=True)

        # Algorithm 1
        if note == 3:
            if self.interval > self.min_interval:
                self.flag = self.m
                self.interval = self.min_interval
                self.m = 0
                self.transmitted = 0
                self.suppressed = 0
            else:
                self.interval = self.min_interval
                self.m = 0
        elif self.flag is not None:
            self.interval = self.min_interval * pow(2, self.flag)
            self.m = self.flag
            self.flag = None
        else:
            self.interval = self.min_interval
            self.m = 0
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

        self.counter = 0
        self.redundancy_constant = self.calculate_k()
        self._schedule_event_at_t_and_i()

    def _schedule_event_at_t_and_i(self):
        # Algorithm 3
        slot_duration_ms = self.settings.tsch_slotDuration * 1000  # convert to ms
        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength
        NcellsC = self.toint_division(self.interval, slotframe_duration_ms, is_floor=True)
        half_ncells = self.toint_division(NcellsC, 2)

        self.Nnbr = len(self.mote.rpl.of.neighbors) if hasattr(
            self.mote.rpl.of, 'neighbors') else 0

        is_t_in_cell = True
        if self.interval == self.min_interval or self.suppressed > 0:
            self.t_start = 0
            self.t_end = half_ncells - ((half_ncells / (self.Nnbr + 1)) * self.suppressed)
            self.t_end = max(min(half_ncells, self.t_end), 0)
        elif self.transmitted > 0:
            self.t_start = half_ncells + (((self.Nnbr + 1) / half_ncells) * self.transmitted)
            self.t_start = max(min(NcellsC, self.t_start), half_ncells)
            self.t_end = NcellsC
        else:
            is_t_in_cell = False
            half_interval = old_div(self.interval, 2)
            self.t_start = half_interval
            self.t_end = self.interval

        if is_t_in_cell:
            self.t_start = self.t_start * slotframe_duration_ms
            self.t_end = self.t_end * slotframe_duration_ms

        logss = f'\nLOG, {self.t_start}, {self.t_end}, {self.interval}, \n'

        self.t = random.uniform(self.t_start, self.t_end)
        assert self.t_start <= self.t_end <= self.interval, logss
        assert self.t_start <= self.t <= self.t_end, logss

        self.listen_period = self.t - self.t_start

        self.ops = self.getOpsMC()
        self.ops_asn = self.engine.getAsn()

        # asn = seconds / tsch_slotDuration (s) = ms / slot_duration_ms
        cur_asn = self.engine.getAsn()
        asn_start = cur_asn + \
            self.toint_division(self.t_start, slot_duration_ms)
        asn_t = cur_asn + self.toint_division(self.t, slot_duration_ms)
        asn_end = cur_asn + self.toint_division(self.t_end, slot_duration_ms)
        asn_i = cur_asn + self.toint_division(self.interval, slot_duration_ms)

        assert asn_start >= 0 and asn_end >= 0 and asn_t >= 0 and asn_i >= 0, logss

        def t_callback():
            self.is_dio_sent = False
            if self.counter < self.redundancy_constant:
                self.is_dio_sent = True
                self.transmitted += 1
                self.user_callback()
            else:
                self.suppressed += 1

            if self.is_dio_sent:
                self.DIOtransmit += 1
            else:
                self.DIOsurpress += 1
            self.calculate_ptransmit()

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
            self.engine.scheduleAtAsn(
                asn=self.correctASN(asn_end),
                cb=end_t,
                uniqueTag=self.unique_tag_base + u'_at_end_t',
                intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        # ========================

        def i_callback():
            self.calculate_multiple_p()

            self.log_result()

            self.interval = self.interval * 2
            self.m += 1
            self.interval = max(
                min(self.max_interval, self.interval), self.min_interval)
            if self.max_interval == self.interval: self.m = self.i_max
            self._start_next_interval()

        def end_t_i_callback():
            end_t()
            i_callback()

        self.engine.scheduleAtAsn(
            asn=self.correctASN(asn_i),
            cb=i_callback if self.t_end < self.interval else end_t_i_callback,
            uniqueTag=self.unique_tag_base + u'_at_i',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

    def calculate_multiple_p(self):
        self.calculate_pbusy()
        self.calculate_psent()
        self.calculate_pqu()

    def calculate_preset(self):
        self.preset = self.Nreset / self.Nstates
        assert 0 <= self.preset <= 1
        self.pstable = 1 - self.preset

    def calculate_ptransmit(self):
        self.ptransmit = self.DIOtransmit / self.Nstates
        assert 0 <= self.ptransmit <= 1

    def calculate_psent(self):
        self.pfailed = self.mote.rpl.get_failed_dio(True, True)
        if self.pfailed is None:
            self.psent = 0
            self.pfailed = 0
            return
        self.psent = 1 - self.pfailed
        assert 0 <= self.psent <= 1

    def calculate_pqu(self):
        self.pqu = self.mote.tsch.get_queue_usage()
        assert 0 <= self.pqu <= 1

    def calculate_pbusy(self):
        curr = self.getOpsMC()
        curr_asn = self.engine.getAsn()
        diff_asn = curr_asn - self.ops_asn
        self.Ncells = self.toint_division(diff_asn, self.settings.tsch_slotframeLength, is_floor=True)

        if self.ops is None or curr is None or self.Ncells == 0:
            self.pbusy = 0
            return

        self.used = curr - self.ops
        if self.Ncells < self.used: self.Ncells = self.used
        occ = self.used / self.Ncells
        self.pbusy = occ
        assert 0 <= self.pbusy <= 1

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

    def toint_division(self, a, b, is_floor=False):
        if is_floor:
            return int(math.floor(a / b))
        return int(math.ceil(a / b))

    def log_result(self, is_reset=False):
        base = {
            'state': self.Nstates,
            'is_reset': is_reset,
            'preset': self.preset,
            'Nreset': self.Nreset,

            'pqu_prev': None,
            'pqu': self.pqu,
            'pbusy_prev': None,
            'pbusy': self.pbusy,
            'psent_prev': None,
            'psent': self.psent,
            'pfailed': self.pfailed,
            'preset': self.preset,
            'pstable': self.pstable,
            'ptransmit': self.ptransmit,

            'redundancy_constant': self.redundancy_constant,
            't': self.t,
            'interval': self.interval,
            'Nnbr': self.Nnbr,
            'Ncells': self.Ncells,
            'used': self.used,
            'm': self.m
        }

        more = {
            'counter': self.counter,
            'is_dio_sent': self.is_dio_sent,
            'count_dio_trickle': self.mote.rpl.count_dio_trickle,
            'reward': None,
        }

        result = {**base} if is_reset else {**base, **more}
        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )

    def calculate_k(self):
        self.Nnbr = len(self.mote.rpl.of.neighbors) if hasattr(
            self.mote.rpl.of, 'neighbors') else 0

        # Algorithm 2
        if self.m == 0:
            k = min(self.Nnbr + 1, 10)
        elif self.m > 0 and self.m <= self.i_max/2:
            k = min(self.toint_division(self.Nnbr + 1, 2), 10)
        else:
            k = min(self.Nnbr + 1, 10)
        return k