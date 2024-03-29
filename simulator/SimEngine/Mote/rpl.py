""" RPL Implementation
references:
- IETF RFC 6550
- IETF RFC 6552
- IETF RFC 6553
- IETF RFC 8180

note:
- global repair is not supported
"""
from __future__ import absolute_import
from __future__ import division

# =========================== imports =========================================

from builtins import str
from builtins import object
from past.utils import old_div
import random
import math
import sys

import netaddr
import numpy

# Mote sub-modules

# Simulator-wide modules
import SimEngine
from . import MoteDefines as d
from .trickle_timer import TrickleTimer
from .trickle_qtrickle import QTrickle
from .trickle_riata import RiataTrickle
from .trickle_acpb import ACPBTrickle

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================


class Rpl(object):
    # locally-defined constants
    DEFAULT_DIS_INTERVAL_SECONDS = 60

    def __init__(self, mote):

        # store params
        self.mote = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log = SimEngine.SimLog.SimLog().log

        self.trickle_method = self.settings.trickle_method or ""

        if self.trickle_method == 'qt':
            trickle_class = QTrickle
        elif self.trickle_method == 'riata':
            trickle_class = RiataTrickle
        elif self.trickle_method == 'ac':
            trickle_class = ACPBTrickle
        else:
            trickle_class = TrickleTimer

        # local variables
        self.dodagId = None
        self.of = RplOFNone(self)
        self.trickle_timer = trickle_class(
            callback=self._send_DIO_Trickle,
            mote=self.mote
        )
        self.parentChildfromDAOs = {}      # dictionary containing parents of each node
        self._tx_stat = {}      # indexed by mote_id
        self.dis_mode = self._get_dis_mode()

        self.count_dis = 0
        self.count_dio = 0
        self.count_dao = 0
        self.count_dio_trickle = 0
        self.DIOtransmit_all = {}
        self.first_joined = False
        self.received_DIS = {}

    # ======================== public ==========================================

    # getters/setters

    def get_rank(self):
        return self.of.rank

    def increase_dio_actual_sent(self, pos, dio_id):
        if dio_id is None:
            return

        if pos not in self.DIOtransmit_all:
            self.DIOtransmit_all[pos] = {dio_id}
        else:
            self.DIOtransmit_all[pos].add(dio_id)

    def getDagRank(self):
        if self.of.rank is None:
            return None
        else:
            return int(old_div(self.of.rank, d.RPL_MINHOPRANKINCREASE))

    def addParentChildfromDAOs(self, parent_addr, child_addr):
        self.parentChildfromDAOs[child_addr] = parent_addr

    def getPreferredParent(self):
        # return the MAC address of the current preferred parent
        return self.of.get_preferred_parent()

    # admin

    def start_or_reset_trickle_timer(self, note):
        if self.dodagId:
            if self.trickle_timer.interval == 0:
                self.trickle_timer.start(note)
            else:
                self.trickle_timer.reset(note)
    
    def get_set_size(self, data):
        if data:
            return len(set(data))
        return 0

    def get_failed_dio(self, is_prob=False, is_trickle=False):
        if is_trickle:
            count_ = self.count_dio_trickle
            transmit_ = self.get_set_size(self.DIOtransmit_all.get(7, 0))
        else:
            count_ = self.count_dio
            transmit_ = self.get_set_size(self.DIOtransmit_all.get(6, 0))
        count_ = int(count_)
        transmit_ = int(transmit_)

        failed = count_ - transmit_
        assert failed >= 0 # check
        if count_ == 0: return None # havent send anything
        if is_prob: failed = failed/count_
        return failed

    def last_slotframe_callback(self):
        if self.mote.dagRoot:
            return

        if self.of.get_preferred_parent() is None:
            return

        DIOsurpress = self.trickle_timer.DIOsurpress

        result = {
            'count_dio': self.count_dio,
            'count_dio_trickle': self.count_dio_trickle,
            'failed_dio': self.get_failed_dio(),
            'failed_dio_trickle': self.get_failed_dio(is_trickle=True),
            'trickle_surpress': DIOsurpress,
        }

        for k in self.DIOtransmit_all.keys():
            new_key = f'DIOtransmit_{k}'
            result[new_key] = self.get_set_size(self.DIOtransmit_all[k])

        if hasattr(self.trickle_timer, 'ql_table'):
            result['ql_table'] = self.trickle_timer.ql_table

        # log
        self.log(
            SimEngine.SimLog.LOG_LAST_SLOTFRAME,
            {
                u'_mote_id': self.mote.id,
                u'result': result,
            }
        )
    
    def last_slotframe_trigger(self):
        tag_ = str(self.mote.id) + u'ambr'
        if self.engine.is_scheduled(tag_):
            return

        cur_asn = self.engine.getAsn()
        slotframe_iteration = int(old_div(cur_asn, self.settings.tsch_slotframeLength))
        self.end_slotframe = self.settings.exec_numSlotframesPerRun
        left_slotframe = self.end_slotframe - slotframe_iteration - 1

        asn_end = cur_asn + (self.settings.tsch_slotframeLength * left_slotframe)
        if asn_end == self.engine.getAsn():
            # schedule the event at the next ASN since we cannot schedule it at
            # the current ASN
            asn_end = self.engine.getAsn() + 1
            
        self.engine.scheduleAtAsn(
            asn=asn_end,
            cb=self.last_slotframe_callback,
            uniqueTag=tag_,
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS
        )

    def start(self):
        if self.mote.dagRoot:
            self.dodagId = self.mote.get_ipv6_global_addr()
            self.of.set_rank(d.RPL_MINHOPRANKINCREASE)
            # now start a new RPL instance; reset the timer as per Section 8.3 of
            # RFC 6550
            self.start_or_reset_trickle_timer(1)

        else:
            if self.settings.rpl_of:
                # update OF with one specified in config.json
                of_class = u'Rpl{0}'.format(self.settings.rpl_of)
                self.of = getattr(sys.modules[__name__], of_class)(self)
            if self.dis_mode != u'disabled':
                # the destination address of the first DIS is determined based
                # on self.dis_mode
                if self.dis_mode == u'dis_unicast':
                    # join_proxy is a possible parent
                    dstIp = str(self.mote.tsch.join_proxy.ipv6_link_local())
                elif self.dis_mode == u'dis_broadcast':
                    dstIp = d.IPV6_ALL_RPL_NODES_ADDRESS
                else:
                    raise NotImplementedError()
                self.send_DIS(dstIp)
                self.start_dis_timer()
                self.last_slotframe_trigger()

    def stop(self):
        assert not self.mote.dagRoot
        self.dodagId = None
        self.trickle_timer.stop()
        self.stop_dis_timer()

    def indicate_tx(self, cell, dstMac, isACKed):
        self.of.update_etx(cell, dstMac, isACKed)

    def indicate_preferred_parent_change(self, old_preferred, new_preferred):
        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_CHURN,
            {
                "_mote_id":        self.mote.id,
                "rank":            self.of.rank,
                "preferredParent": new_preferred
            }
        )

        if new_preferred is None:
            assert old_preferred
            # stop the DAO timer
            self._stop_sendDAO()

            # don't change the clock source

            # trigger a DIO which advertises infinite rank
            self._send_DIO_disreq(dio_type='no_parent')

            # stop the trickle timer
            self.trickle_timer.stop()

            # stop the EB transmission
            self.mote.tsch.stopSendingEBs()

            # start the DIS timer
            self.start_dis_timer()
        else:
            # trigger DAO
            self._schedule_sendDAO(firstDAO=True)

            # use the new parent as our clock source
            self.mote.tsch.clock.sync(new_preferred)

            # reset trickle timer to inform new rank quickly
            self.start_or_reset_trickle_timer(2)
        # trigger 6P ADD if parent changed
        self.mote.sf.indication_parent_change(old_preferred, new_preferred)

    def local_repair(self):
        self.of.reset()
        assert (
            (self.of.rank is None)
            or
            (self.of.rank == d.RPL_INFINITE_RANK)
        )
        self.log(
            SimEngine.SimLog.LOG_RPL_LOCAL_REPAIR,
            {
                "_mote_id":        self.mote.id
            }
        )
        self.dodagId = None

    # === DIS

    def action_receiveDIS(self, packet):
        self.log(
            SimEngine.SimLog.LOG_RPL_DIS_RX,
            {
                "_mote_id":  self.mote.id,
                "packet":    packet,
            }
        )
        if self.dodagId is None:
            # ignore DIS
            pass
        else:
            reset = False
            if self.mote.is_my_ipv6_addr(packet[u'net'][u'dstIp']):
                # unicast DIS; send unicast DIO back to the source
                self._send_DIO_disreq(packet[u'net'][u'srcIp'])
            elif packet[u'net'][u'dstIp'] == d.IPV6_ALL_RPL_NODES_ADDRESS:
                # broadcast DIS
                self.mote.tsch.set_sw_after_dis()
                self._send_DIO_disreq()

                if getattr(self.settings, "algo_dis_prio", 0) in [2, 3]:
                    neighbor_mac = packet[u'mac'][u'srcMac']
                    if neighbor_mac not in self.received_DIS:
                        self.received_DIS[neighbor_mac] = 0
                    self.received_DIS[neighbor_mac] += 1

                    if self.received_DIS[neighbor_mac] >= 2:
                        reset = True
                        self.received_DIS = {}
                else:
                    reset = True
            else:
                # shouldn't happen
                assert False
            
            if reset:
                self.start_or_reset_trickle_timer(3)

    def _get_dis_mode(self):
        if u'dis_unicast' in self.settings.rpl_extensions:
            assert u'dis_broadcast' not in self.settings.rpl_extensions
            return u'dis_unicast'
        elif 'dis_broadcast' in self.settings.rpl_extensions:
            assert u'dis_unicast' not in self.settings.rpl_extensions
            return u'dis_broadcast'
        else:
            return u'disabled'

    @property
    def dis_timer_is_running(self):
        return self.engine.is_scheduled(str(self.mote.id) + u'dis')

    def start_dis_timer(self):
        self.engine.scheduleIn(
            delay=self.settings.rpl_disPeriod,
            cb=self.handle_dis_timer,
            uniqueTag=str(self.mote.id) + u'dis',
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS
        )

    def stop_dis_timer(self):
        self.engine.removeFutureEvent(str(self.mote.id) + u'dis')

    def handle_dis_timer(self):
        self.send_DIS(d.IPV6_ALL_RPL_NODES_ADDRESS)
        self.start_dis_timer()

    def send_DIS(self, dstIp):
        assert dstIp is not None
        dis = {
            u'type': d.PKT_TYPE_DIS,
            u'net': {
                u'srcIp':         str(self.mote.get_ipv6_link_local_addr()),
                u'dstIp':         dstIp,
                u'packet_length': d.PKT_LEN_DIS
            },
            u'app': {}
        }
        self.log(
            SimEngine.SimLog.LOG_RPL_DIS_TX,
            {
                u'_mote_id':  self.mote.id,
                u'packet':    dis,
            }
        )
        self.count_dis += 1
        self.mote.sixlowpan.sendPacket(dis)

    # === DIO

    def _send_DIO_disreq(self, dst=None, dio_type='dis'):
        # DZAKY except qt not use dis req
        req = False
        if getattr(self.settings, "algo_dis_prio", 0) in [1, 3]:
            req = True

        self._send_DIO(dstIp=dst, dis_req=req, dio_type=dio_type)

    def _send_DIO_Trickle(self):
        self.count_dio_trickle += 1
        self._send_DIO(dstIp=None, is_trickle=True, dio_type='trickle')

    def _send_DIO(self, dstIp=None, is_trickle=False, dis_req=False, dio_type=None):
        if not is_trickle and self.dodagId is None:
            # seems we performed local repair
            return

        dio_id = None
        if dstIp is None:
            self.count_dio += 1
            dio_id = self.count_dio

        dio = self._create_DIO(dstIp, is_trickle, dio_id, dis_req, dio_type)

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_TX,
            {
                u'_mote_id':  self.mote.id,
                u'packet':    dio,
            }
        )

        # DZAKY: DIO goes here (1)
        self.mote.sixlowpan.sendPacket(dio)

    def _create_DIO(self, dstIp=None, is_trickle=False, dio_id=None, dis_req=False, dio_type=None):

        assert self.dodagId is not None

        if dstIp is None:
            dstIp = d.IPV6_ALL_RPL_NODES_ADDRESS

        if self.of.rank is None:
            rank = d.RPL_INFINITE_RANK
        else:
            rank = self.of.rank

        # create
        newDIO = {
            u'type':              d.PKT_TYPE_DIO,
            u'app': {
                u'rank':          rank,
                u'dodagId':       self.dodagId,
                u'dio_id':        dio_id,
                u'dis_req':       dis_req,
                u'is_trickle':    int(is_trickle),
                u'dio_type':      dio_type
            },
            u'net': {
                u'srcIp':         self.mote.get_ipv6_link_local_addr(),
                u'dstIp':         dstIp,
                u'packet_length': d.PKT_LEN_DIO
            }
        }

        return newDIO

    def action_receiveDIO(self, packet):

        assert packet[u'type'] == d.PKT_TYPE_DIO

        # abort if I'm not sync'ed (I cannot decrypt the DIO)
        if not self.mote.tsch.getIsSync():
            return

        # abort if I'm not join'ed (I cannot decrypt the DIO)
        if not self.mote.secjoin.getIsJoined():
            return

        # abort if I'm the DAGroot (I don't need to parse a DIO)
        if self.mote.dagRoot:
            return

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_RX,
            {
                u'_mote_id':  self.mote.id,
                u'packet':    packet,
            }
        )

        # handle the infinite rank
        if packet[u'app'][u'rank'] == d.RPL_INFINITE_RANK:
            if self.dodagId is None:
                # ignore this DIO
                return
            else:
                # if the DIO has the infinite rank, reset the Trickle timer
                self.start_or_reset_trickle_timer(4)

        neighbor = self.of._find_neighbor(packet[u'mac'][u'srcMac'])
        if neighbor:
            if (neighbor[u'advertised_rank'] == packet[u'app'][u'rank']):
                # consistent
                self.trickle_timer.increment_counter()
                # print(self.mote.id, neighbor[u'mac_addr'], packet[u'app'][u'rank'], neighbor[u'advertised_rank'], self.trickle_timer.counter)

        # feed our OF with the received DIO
        self.of.update(packet)

        if self.getPreferredParent() is not None:
            if packet[u'app'][u'dodagId'] != self.dodagId:
                # (re)join the RPL network
                self.join_dodag(packet[u'app'][u'dodagId'], packet[u'app'][u'dio_type'])

    def join_dodag(self, dodagId=None, dio_type=None):
        # re-join the DODAG without receiving a DIO
        assert dodagId is not None
        self.dodagId = dodagId
        self.mote.add_ipv6_prefix(d.IPV6_DEFAULT_PREFIX)
        self.start_or_reset_trickle_timer(5)
        self.stop_dis_timer()

        if not self.first_joined:
            self.first_joined = True
            self.log(
                SimEngine.SimLog.LOG_RPL_JOINED,
                {
                    u'_mote_id': self.mote.id,
                    u'dio_type': dio_type
                }
            )

    # === DAO

    def _schedule_sendDAO(self, firstDAO=False):
        """
        Schedule to send a DAO sometimes in the future.
        """

        assert self.mote.dagRoot is False

        # abort if DAO disabled
        if self.settings.rpl_daoPeriod == 0:
           # secjoin never completes if downward traffic is not supported by
            # DAO
            assert self.settings.secjoin_enabled is False

            # start sending EBs and application packets.
            self.mote.tsch.startSendingEBs()
            self.mote.app.startSendingData()
            return

        asnNow = self.engine.getAsn()

        if firstDAO:
            asnDiff = 1
        else:
            asnDiff = int(math.ceil(
                old_div(random.uniform(
                    0.8 * self.settings.rpl_daoPeriod,
                    1.2 * self.settings.rpl_daoPeriod
                ), self.settings.tsch_slotDuration))
            )

        # schedule sending a DAO
        self.engine.scheduleAtAsn(
            asn=asnNow + asnDiff,
            cb=self._action_sendDAO,
            uniqueTag=(self.mote.id, u'_action_sendDAO'),
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS,
        )

    def _stop_sendDAO(self):
        self.engine.removeFutureEvent((self.mote.id, u'_action_sendDAO'))

    def _action_sendDAO(self):
        """
        Enqueue a DAO and schedule next one.
        """

        if self.of.get_preferred_parent() is None:
            # stop sending DAO
            return

        # enqueue
        self._action_enqueueDAO()

        # the root now knows a source route to me
        # I can serve as join proxy: start sending DIOs and EBs
        # I can send data back-and-forth with an app
        self.mote.tsch.startSendingEBs()    # mote
        self.mote.app.startSendingData()    # mote

        # schedule next DAO
        self._schedule_sendDAO()

    def _action_enqueueDAO(self):
        """
        enqueue a DAO into TSCH queue
        """

        assert not self.mote.dagRoot

        if self.dodagId is None:
            # seems we've lost all the candidate parents; do nothing
            return

        # abort if not ready yet
        if self.mote.clear_to_send_EBs_DATA() == False:
            return

        parent_mac_addr = netaddr.EUI(self.of.get_preferred_parent())
        prefix = netaddr.IPAddress(d.IPV6_DEFAULT_PREFIX)
        parent_ipv6_addr = str(parent_mac_addr.ipv6(prefix))

        # create
        newDAO = {
            u'type':                d.PKT_TYPE_DAO,
            u'app': {
                u'parent_addr':     parent_ipv6_addr,
            },
            u'net': {
                u'srcIp':           self.mote.get_ipv6_global_addr(),
                u'dstIp':           self.dodagId,       # to DAGroot
                u'packet_length':   d.PKT_LEN_DAO,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DAO_TX,
            {
                u'_mote_id': self.mote.id,
                u'packet':   newDAO,
            }
        )

        # remove other possible DAOs from the queue
        self.mote.tsch.remove_packets_in_tx_queue(type=d.PKT_TYPE_DAO)

        self.count_dao += 1
        # send
        self.mote.sixlowpan.sendPacket(newDAO)

    def action_receiveDAO(self, packet):
        """
        DAGroot receives DAO, store parent/child relationship for source route calculation.
        """

        assert self.mote.dagRoot

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DAO_RX,
            {
                u'_mote_id': self.mote.id,
                u'packet':   packet,
            }
        )

        # store parent/child relationship for source route calculation
        self.addParentChildfromDAOs(
            parent_addr=packet[u'app'][u'parent_addr'],
            child_addr=packet[u'net'][u'srcIp']
        )

    # source route

    def computeSourceRoute(self, dst_addr):
        assert self.mote.dagRoot
        try:
            sourceRoute = []
            cur_addr = dst_addr
            while self.mote.is_my_ipv6_addr(cur_addr) is False:
                sourceRoute += [cur_addr]
                cur_addr = self.parentChildfromDAOs[cur_addr]
                if cur_addr in sourceRoute:
                    # routing loop is detected; cannot return an effective
                    # source-routing header
                    returnVal = None
                    break
        except KeyError:
            returnVal = None
        else:
            # reverse (so goes from source to destination)
            sourceRoute.reverse()

            returnVal = sourceRoute

        return returnVal


class RplOFBase(object):
    def __init__(self, rpl):
        self.rpl = rpl
        self.rank = None
        self.preferred_parent = None

    def reset(self):
        self.rank = None
        old_parent_mac_addr = self.get_preferred_parent()
        self.preferred_parent = None
        self.rpl.indicate_preferred_parent_change(
            old_preferred=old_parent_mac_addr,
            new_preferred=None
        )

    def update(self, dio):
        pass

    def update_etx(self, cell, mac_addr, isACKed):
        pass

    def get_preferred_parent(self):
        return self.preferred_parent

    def poison_rpl_parent(self, mac_addr):
        pass


class RplOFNone(RplOFBase):
    def set_rank(self, new_rank):
        self.rank = new_rank

    def set_preferred_parent(self, new_preferred_parent):
        self.preferred_parent = new_preferred_parent


class RplOF0(RplOFBase):

    # Constants defined in RFC 6550
    INFINITE_RANK = 65535

    # Constants defined in RFC 8180
    UPPER_LIMIT_OF_ACCEPTABLE_ETX = 3
    MINIMUM_STEP_OF_RANK = 1
    MAXIMUM_STEP_OF_RANK = 9

    # Custom constants
    MAX_NUM_OF_CONSECUTIVE_FAILURES_WITHOUT_SUCCESS = 10
    ETX_DEFAULT = UPPER_LIMIT_OF_ACCEPTABLE_ETX
    # if we have a "good" link to the parent, stay with the parent even if the
    # rank of the parent is worse than the best neighbor by more than
    # PARENT_SWITCH_RANK_THRESHOLD. rank_increase is computed as per Section
    # 5.1.1. of RFC 8180.
    ETX_GOOD_LINK = 2
    PARENT_SWITCH_RANK_INCREASE_THRESHOLD = (
        ((3 * ETX_GOOD_LINK) - 2) * d.RPL_MINHOPRANKINCREASE
    )
    # The number of transmissions that is needed for ETX calculation
    ETX_NUM_TX_CUTOFF = 100

    def __init__(self, rpl):
        super(RplOF0, self).__init__(rpl)
        self.neighbors = []

        # short hand
        self.mote = self.rpl.mote
        self.engine = self.rpl.engine
        self.connectivity = self.engine.connectivity

    @property
    def parents(self):
        # a parent should have a lower rank than us by MinHopRankIncrease at
        # least. See section 3.5.1 of RFC 6550:
        #    "MinHopRankIncrease is the minimum increase in Rank between a node
        #     and any of its DODAG parents."
        _parents = []
        for neighbor in self.neighbors:
            if self._calculate_rank(neighbor) is None:
                # skip this one
                continue

            if (
                (self.rank is None)
                or
                (
                    d.RPL_MINHOPRANKINCREASE <=
                    self.rank - neighbor[u'advertised_rank']
                )
            ):
                _parents.append(neighbor)

        return _parents

    def reset(self):
        self.neighbors = []
        super(RplOF0, self).reset()

    def update(self, dio):
        mac_addr = dio[u'mac'][u'srcMac']
        rank = dio[u'app'][u'rank']

        # update neighbor's rank
        neighbor = self._find_neighbor(mac_addr)
        if neighbor is None:
            neighbor = self._add_neighbor(mac_addr)
        self._update_neighbor_rank(neighbor, rank)

        # if we received the infinite rank from our preferred parent,
        # invalidate our rank
        if (
            (self.preferred_parent == neighbor)
            and
            (rank == d.RPL_INFINITE_RANK)
        ):
            self.rank = None

        # change preferred parent if necessary
        self._update_preferred_parent()

    def get_preferred_parent(self):
        if self.preferred_parent is None:
            return None
        else:
            return self.preferred_parent[u'mac_addr']

    def poison_rpl_parent(self, mac_addr):
        if mac_addr is None:
            neighbor = None
        else:
            neighbor = self._find_neighbor(mac_addr)

        if neighbor:
            self._update_neighbor_rank(neighbor, d.RPL_INFINITE_RANK)
            self.rank = None
            self._update_preferred_parent()

    def update_etx(self, cell, mac_addr, isACKed):
        assert mac_addr != d.BROADCAST_ADDRESS
        assert d.CELLOPTION_TX in cell.options

        neighbor = self._find_neighbor(mac_addr)
        if neighbor is None:
            # we've not received DIOs from this neighbor; ignore the neighbor
            return

        if cell.mac_addr is None:
            # we calculate ETX only on dedicated cells
            # XXX: Although it'd be better to exclude cells having
            # SHARED bit on as well, this is not good for the
            # autonomous cell defined by MSF.
            return

        neighbor[u'numTx'] += 1
        if isACKed is True:
            neighbor[u'numTxAck'] += 1

        if neighbor[u'numTx'] >= self.ETX_NUM_TX_CUTOFF:
            # update ETX
            assert neighbor[u'numTxAck'] > 0
            neighbor[u'etx'] = float(
                neighbor[u'numTx']) / neighbor[u'numTxAck']
            # reset counters
            neighbor[u'numTx'] = 0
            neighbor[u'numTxAck'] = 0
        elif (
            (neighbor[u'numTxAck'] == 0)
            and
            (
                self.MAX_NUM_OF_CONSECUTIVE_FAILURES_WITHOUT_SUCCESS <=
                neighbor[u'numTx']
            )
        ):
            # set invalid ETX
            neighbor[u'etx'] = self.UPPER_LIMIT_OF_ACCEPTABLE_ETX + 1

        self._update_neighbor_rank_increase(neighbor)
        self._update_preferred_parent()

    def _add_neighbor(self, mac_addr):
        assert self._find_neighbor(mac_addr) is None

        neighbor = {
            u'mac_addr': mac_addr,
            u'advertised_rank': None,
            u'rank_increase': None,
            u'numTx': 0,
            u'numTxAck': 0,
            u'etx': self.ETX_DEFAULT
        }
        self.neighbors.append(neighbor)
        self._update_neighbor_rank_increase(neighbor)
        return neighbor

    def _find_neighbor(self, mac_addr):
        for neighbor in self.neighbors:
            if neighbor[u'mac_addr'] == mac_addr:
                return neighbor
        return None

    def _update_neighbor_rank(self, neighbor, new_advertised_rank):
        neighbor[u'advertised_rank'] = new_advertised_rank

    def _update_neighbor_rank_increase(self, neighbor):
        if neighbor[u'etx'] > self.UPPER_LIMIT_OF_ACCEPTABLE_ETX:
            step_of_rank = None
        else:
            # step_of_rank is strictly positive integer as per RFC6552
            step_of_rank = int((3 * neighbor[u'etx']) - 2)

        if step_of_rank is None:
            # this neighbor will not be considered as a parent
            neighbor[u'rank_increase'] = None
        else:
            assert self.MINIMUM_STEP_OF_RANK <= step_of_rank
            # step_of_rank never exceeds 7 because the upper limit of acceptable
            # ETX is 3, which is defined in Section 5.1.1 of RFC 8180
            assert step_of_rank <= self.MAXIMUM_STEP_OF_RANK
            neighbor[u'rank_increase'] = step_of_rank * \
                d.RPL_MINHOPRANKINCREASE

        if neighbor == self.preferred_parent:
            self.rank = self._calculate_rank(self.preferred_parent)

    def _calculate_rank(self, neighbor):
        if (
            (neighbor is None)
            or
            (neighbor[u'advertised_rank'] is None)
            or
            (neighbor[u'rank_increase'] is None)
        ):
            return None
        elif neighbor[u'advertised_rank'] == self.INFINITE_RANK:
            # this neighbor should be ignored
            return None
        else:
            rank = neighbor[u'advertised_rank'] + neighbor[u'rank_increase']

            if rank > self.INFINITE_RANK:
                return self.INFINITE_RANK
            else:
                return rank

    def _update_preferred_parent(self):
        if (
            (self.preferred_parent is not None)
            and
            (self.preferred_parent[u'advertised_rank'] is not None)
            and
            (self.rank is not None)
            and
            (
                (self.preferred_parent[u'advertised_rank'] - self.rank) <
                d.RPL_PARENT_SWITCH_RANK_THRESHOLD
            )
            and
            (
                self.preferred_parent[u'rank_increase'] <
                self.PARENT_SWITCH_RANK_INCREASE_THRESHOLD
            )
        ):
            # stay with the current parent. the link to the parent is
            # good. but, if the parent rank is higher than us and the
            # difference is more than d.RPL_PARENT_SWITCH_RANK_THRESHOLD, we dump
            # the parent. otherwise, we may create a routing loop.
            return

        try:
            candidate = min(self.parents, key=self._calculate_rank)
            new_rank = self._calculate_rank(candidate)
        except ValueError:
            # self.parents is empty
            candidate = None
            new_rank = None

        if new_rank is None:
            # we don't have any available parent
            new_parent = None
        elif self.rank is None:
            new_parent = candidate
            self.rank = new_rank
        else:
            # (new_rank is not None) and (self.rank is None)
            rank_difference = self.rank - new_rank

            # Section 6.4, RFC 8180
            #
            #   Per [RFC6552] and [RFC6719], the specification RECOMMENDS the
            #   use of a boundary value (PARENT_SWITCH_RANK_THRESHOLD) to avoid
            #   constant changes of the parent when ranks are compared.  When
            #   evaluating a parent that belongs to a smaller path cost than
            #   the current minimum path, the candidate node is selected as the
            #   new parent only if the difference between the new path and the
            #   current path is greater than the defined
            #   PARENT_SWITCH_RANK_THRESHOLD.

            if rank_difference is not None:
                if d.RPL_PARENT_SWITCH_RANK_THRESHOLD < rank_difference:
                    new_parent = candidate
                    self.rank = new_rank
                else:
                    # no change on preferred parent
                    new_parent = self.preferred_parent

        if (
            (new_parent is not None)
            and
            (new_parent != self.preferred_parent)
        ):
            # change to the new preferred parent

            if self.preferred_parent is None:
                old_parent_mac_addr = None
            else:
                old_parent_mac_addr = self.preferred_parent[u'mac_addr']

            self.preferred_parent = new_parent
            if new_parent is None:
                new_parent_mac_addr = None
            else:
                new_parent_mac_addr = self.preferred_parent[u'mac_addr']

            self.rpl.indicate_preferred_parent_change(
                old_preferred=old_parent_mac_addr,
                new_preferred=new_parent_mac_addr
            )

            # reset Trickle Timer # already called in indicate_preferred_parent_change
            # self.rpl.start_or_reset_trickle_timer()
        elif (
            (new_parent is None)
            and
            (self.preferred_parent is not None)
        ):
            self.rpl.local_repair()
        else:
            # do nothing
            pass
