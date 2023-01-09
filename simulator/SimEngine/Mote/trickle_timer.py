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
        self.Nstates = 1
        self.Ncells = 0
        self.Nreset = 0
        self.pfree = 1
        self.poccupancy = 0
        self.preset = 0
        self.pstable = 1
        self.DIOsurpress = 0
        self.DIOtransmit = 0
        self.DIOtransmit_dis = 0
        self.DIOtransmit_collision = 0
        self.m = 0

    @property
    def is_running(self):
        return self.state == self.STATE_RUNNING

    def increment_diotransmit_dis(self, is_broadcast):
        self.DIOtransmit_dis += 1

    def start(self, note=None):
        # Section 4.2:
        #   1.  When the algorithm starts execution, it sets I to a value in
        #       the range of [Imin, Imax] -- that is, greater than or equal to
        #       Imin and less than or equal to Imax.  The algorithm then begins
        #       the first interval.
        self.state = self.STATE_RUNNING
        self.m = 0
        self.interval = self.min_interval #random.randint(self.min_interval, self.max_interval)
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
        self.m = 0
        self.Nreset += 1
        self.preset = self.Nreset / self.Nstates
        self.pstable = 1 - self.preset

        if self.min_interval < self.interval:
            self.interval = self.min_interval
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

    def _start_next_interval(self):
        if self.state == self.STATE_STOPPED:
            return

        # reset the counter
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_i')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_start_t')
        self.engine.removeFutureEvent(self.unique_tag_base + u'_at_end_t')
        self.counter = 0
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

        t_min = old_div(self.interval, 2)
        t_max = self.interval
        t_range = t_max - t_min
        self.t = random.uniform(t_min, t_max)
        self.listen_period = self.t - t_min

        slotframe_duration_ms = slot_duration_ms * self.settings.tsch_slotframeLength
        self.Ncells = max(int(math.ceil(old_div(t_range, slotframe_duration_ms))), 1)

        cur_asn = self.engine.getAsn()
        # asn = seconds / tsch_slotDuration (s) = ms / slot_duration_ms
        asn_start = cur_asn + int(math.ceil(old_div(t_min, slot_duration_ms)))
        asn = cur_asn + int(math.ceil(old_div(self.t, slot_duration_ms)))

        if asn == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn = self.engine.getAsn() + 1

        if asn_start == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn_start = self.engine.getAsn() + 1

        def t_callback():
            self.mote.tsch.set_is_dio_sent(False)
            self.is_dio_sent = False
            if self.counter < self.redundancy_constant or self.redundancy_constant == 0:
                #  Section 4.2:
                #    4.  At time t, Trickle transmits if and only if the
                #        counter c is less than the redundancy constant k.
                self.is_dio_sent = True
                self.user_callback()
            else:
                # do nothing
                pass

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
            asn=asn,
            cb=t_callback,
            uniqueTag=self.unique_tag_base + u'_at_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        self.engine.scheduleAtAsn(
            asn=asn_start,
            cb=start_t,
            uniqueTag=self.unique_tag_base + u'_at_start_t',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        if t_max < self.interval:
            asn_end = cur_asn + int(math.ceil(old_div(t_max, slot_duration_ms)))
            if asn_end == self.engine.getAsn():
                # schedule the event at the next ASN since we cannot schedule it at
                # the current ASN
                asn_end = self.engine.getAsn() + 1

            self.engine.scheduleAtAsn(
                asn=asn_end,
                cb=end_t,
                uniqueTag=self.unique_tag_base + u'_at_end_t',
                intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

        # ========================

        asn = self.engine.getAsn() + int(math.ceil(old_div(self.interval, slot_duration_ms)))

        def i_callback():
            used = None
            occ = None
            if self.end_t_record is not None and self.start_t_record is not None:
                dio_sent = int(self.mote.tsch.is_dio_sent) * \
                    int(self.is_dio_sent)
                used = max(
                    (self.end_t_record - self.start_t_record) - dio_sent, 0)
                occ = used / self.Ncells
                self.poccupancy = occ
                self.pfree = 1 - self.poccupancy

            if self.is_dio_sent:
                self.DIOtransmit += 1
                if not self.mote.tsch.is_dio_sent:
                    self.DIOtransmit_collision += 1
            else:
                self.DIOsurpress += 1

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
            self.interval = self.interval * 2
            self.m += 1
            self.Nstates += 1
            if self.max_interval < self.interval:
                self.interval = self.max_interval
                self.m = self.i_max
            self._start_next_interval()

        def end_t_i_callback():
            end_t()
            i_callback()

        self.engine.scheduleAtAsn(
            asn=asn,
            cb=i_callback if t_max < self.interval else end_t_i_callback,
            uniqueTag=self.unique_tag_base + u'_at_i',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS)

    def log_result(self):
        count_dis, count_dio, count_dao = self.mote.rpl.get_all_cp()

        minimal_cell = self.mote.tsch.get_cell(0, 0, None, 0)
        all_ops = -1
        if minimal_cell:
            all_ops = minimal_cell.all_ops

        result = {
            'state': self.Nstates,
            'm': self.m,
            'pfree': self.pfree,
            'poccupancy': self.poccupancy,
            'DIOtransmit': self.DIOtransmit,
            'DIOsurpress': self.DIOsurpress,
            'Nreset': self.Nreset,
            'preset': self.preset,
            'pstable': self.pstable,
            'counter': self.counter,
            'k': self.redundancy_constant,
            'listen_period': self.listen_period,
        }

        self.log(
            SimEngine.SimLog.LOG_TRICKLE,
            {
                u'_mote_id':       self.mote.id,
                u'result':         result,
            }
        )
