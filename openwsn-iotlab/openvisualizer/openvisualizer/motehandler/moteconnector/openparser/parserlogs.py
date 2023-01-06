# Copyright (c) 2010-2013, Regents of the University of California.
# All rights reserved.
#
# Released under the BSD 3-Clause license as published at the link below.
# https://openwsn.atlassian.net/wiki/display/OW/License

from appdirs import user_data_dir
import logging
import struct
from datetime import datetime
from openvisualizer.utils import get_log_path, write_to_log
import verboselogs
from enum import IntEnum

from openvisualizer.motehandler.moteconnector.openparser.parser import Parser
from openvisualizer.motehandler.moteconnector.openparser.parserexception import ParserException

verboselogs.install()

log = logging.getLogger('ParserLogs')
log.setLevel(logging.ERROR)
log.addHandler(logging.NullHandler())


class ParserLogs(Parser):
    HEADER_LENGTH = 1
    def_len = 2+1+1+4+4

    class LogSeverity(IntEnum):
        SEVERITY_VERBOSE = ord('V')
        SEVERITY_INFO = ord('I')
        SEVERITY_WARNING = ord('W')
        SEVERITY_SUCCESS = ord('U')
        SEVERITY_ERROR = ord('E')
        SEVERITY_CRITICAL = ord('C')

    def __init__(self, severity, stack_defines):
        assert self.LogSeverity(severity)

        # log
        log.debug("create instance")

        # initialize parent class
        super(ParserLogs, self).__init__(self.HEADER_LENGTH)

        # store params
        self.severity = severity
        self.stack_defines = stack_defines

        # store error info
        self.error_info = {}

        self.filepath = get_log_path()

    # ======================== public ==========================================

    def update_test(self, byte0_1, byte2_3, byte4):
        asn = [
            byte4,
            byte2_3 >> 8,
            byte2_3 % 256,
            byte0_1 >> 8,
            byte0_1 % 256,
        ]
        st = '0x{0}'.format(''.join(["%.2x" % b for b in asn]))
        return asn, st

    def parse_input(self, data):

        # # log
        # log.debug("received data {0}".format(data))

        # parse packet
        data_arg = data[:self.def_len]
        data_only = data[self.def_len-(4*2):]
        try:
            mote_id, component, error_code, arg1, arg2 = struct.unpack('>HBBiI', ''.join([chr(c) for c in data_arg]))
        except struct.error:
            raise ParserException(ParserException.ExceptionType.DESERIALIZE.value,
                                  "could not extract data from {0}".format(data_arg))

        if (component, error_code) in self.error_info.keys():
            self.error_info[(component, error_code)] += 1
        else:
            self.error_info[(component, error_code)] = 1

        if error_code == 0x25:
            # replace args of sixtop command/return code id by string
            arg1 = self.stack_defines["sixtop_returncodes"][arg1]
            arg2 = self.stack_defines["sixtop_states"][arg2]

        component_name = self._translate_component(component)
        log_desc = self._translate_log_description(error_code, arg1, arg2)

        exp_log = False
        pkt_ = {}
        co_name_low = component_name.lower()
        desc_low = log_desc.lower()
        time_format = "%H:%M:%S.%f"

        if "periodic" in co_name_low and "experiment" in desc_low:
            exp_log = True
            asn = None

            try:
                (counter, ambr, is_failed) = struct.unpack('<HHB', ''.join([chr(c) for c in data_only[:-5]]))
            except struct.error:
                log.info("Invalid debug Send-1 {0}".format(data_only))

            try:
                (asn_4, asn_2_3, asn_0_1) = struct.unpack('<BHH', ''.join([chr(c) for c in data_only[-5:]]))
                _, hex = self.update_test(byte0_1=asn_0_1, byte2_3=asn_2_3, byte4=asn_4)
                asn = int(hex, 16)
            except struct.error:
                log.info("Invalid debug Send-2 {0}".format(data_only))

            if asn:
                pkt_["0_state"] = "send"
                pkt_["counter"] = counter
                pkt_["is_failed"] = is_failed
                pkt_["ambr"] = float(ambr)/10000
                pkt_["asn"] = asn
                pkt_["mote_id"] = mote_id
                pkt_["time"] = datetime.now().strftime(time_format)

        elif "rpl" in co_name_low and "experiment" in desc_low:
            exp_log = True
            asn = None

            try:
                (prId2B, myDAGrank, slotDuration) = struct.unpack('<HHB', ''.join([chr(c) for c in data_only[:-5]]))
            except struct.error:
                log.info("Invalid debug RPL-1 {0}".format(data_only))

            try:
                (asn_4, asn_2_3, asn_0_1) = struct.unpack('<BHH', ''.join([chr(c) for c in data_only[-5:]]))
                _, hex = self.update_test(byte0_1=asn_0_1, byte2_3=asn_2_3, byte4=asn_4)
                asn = int(hex, 16)
            except struct.error:
                log.info("Invalid debug RPL-2 {0}".format(data_only))

            if asn:
                pkt_["0_state"] = "join"
                pkt_["asn"] = asn
                pkt_["parent_id"] = prId2B
                pkt_["slot_duration"] = slotDuration
                pkt_["mote_rank"] = myDAGrank
                pkt_["mote_id"] = mote_id
                pkt_["time"] = datetime.now().strftime(time_format)

        elif "trickle" in co_name_low and "experiment" in desc_low:
            exp_log = True
            values = None
            try:
                values = struct.unpack('<BBBBHHHHHHHHHH', ''.join([chr(c) for c in data_only]))
            except struct.error:
                log.info("could not extract data from {0}".format(data_only))

            if values:
                values = list(values)
                if len(values) == 14:
                    pkt_["m"] = values[0]
                    pkt_["Nnbr"] = values[1]
                    pkt_["k"] = values[2]
                    pkt_["counter"] = values[3]
                    pkt_["Nstates"] = values[4]
                    pkt_["Nreset"] = values[5]
                    pkt_["DIOtransmit"] = values[6]
                    pkt_["DIOsurpress"] = values[7]
                    pkt_["DIOtransmit_collision"] = values[8]
                    pkt_["DIOtransmit_dis"] = values[9]
                    pkt_["pfree"] = float(values[10])/10000
                    pkt_["preset"] = float(values[11])/10000
                    pkt_["t_pos"] = float(values[12])/10000
                    pkt_["epsilon"] = float(values[13])/10000

                    pkt_["0_state"] = "trickle"
                    pkt_["mote_id"] = mote_id
                    pkt_["time"] = datetime.now().strftime(time_format)

        if exp_log:
            if pkt_:
                write_to_log(self.filepath, pkt_)
            return 'error', data

        # turn into string
        output = "{MOTEID:x} [{COMPONENT}] {ERROR_DESC}".format(
            COMPONENT=component_name,
            MOTEID=mote_id,
            ERROR_DESC=log_desc,
        )

        # log
        if self.severity == self.LogSeverity.SEVERITY_VERBOSE:
            log.verbose(output)
        elif self.severity == self.LogSeverity.SEVERITY_INFO:
            log.info(output)
        elif self.severity == self.LogSeverity.SEVERITY_WARNING:
            log.warning(output)
        elif self.severity == self.LogSeverity.SEVERITY_SUCCESS:
            log.success(output)
        elif self.severity == self.LogSeverity.SEVERITY_ERROR:
            log.error(output)
        elif self.severity == self.LogSeverity.SEVERITY_CRITICAL:
            log.critical(output)
        else:
            raise SystemError("unexpected severity={0}".format(self.severity))

        return 'error', data

    # ======================== private =========================================

    def _translate_component(self, component):
        try:
            return self.stack_defines["components"][component]
        except KeyError:
            return "unknown component code {0}".format(component)

    def _translate_log_description(self, error_code, arg1, arg2):
        try:
            return self.stack_defines["log_descriptions"][error_code].format(
                arg1, arg2)
        except KeyError:
            return "unknown error {0} arg1={1} arg2={2}".format(error_code, arg1, arg2)
