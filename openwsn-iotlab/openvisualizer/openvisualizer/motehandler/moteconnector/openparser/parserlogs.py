# Copyright (c) 2010-2013, Regents of the University of California.
# All rights reserved.
#
# Released under the BSD 3-Clause license as published at the link below.
# https://openwsn.atlassian.net/wiki/display/OW/License

import logging
import struct

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
        
    # returns a string with the decimal value of a uint16_t
    @staticmethod
    def bytes_to_string(bytestring):
        string = ''
        i = 0

        for byte in bytestring:
            string = format(eval('{0} + {1} * 256 ** {2}'.format(string, byte, i)))
            i = i + 1

        return string

    @staticmethod
    def bytes_to_addr(bytestring):
        string = ''

        for byte in bytestring:
            string = string + '{:02x}'.format(byte)

        return string
        
    # ======================== public ==========================================

    def parse_input(self, data):

        # log
        log.debug("received data {0}".format(data))

        asn = [ 0, 0, 0, 0, 0]

        # parse packet
        try:
            mote_id, asn0,asn1,asn2,asn3,asn4, component, error_code, arg1, arg2 = struct.unpack('>HBBBBBBBhH', ''.join([chr(c) for c in data]))
        except struct.error:
            raise ParserException(ParserException.ExceptionType.DESERIALIZE.value,
                                 "could not extract data from {0}".format(data))
                           
        asn = ParserLogs.bytes_to_string(data[2:7])  # asn (treated separately)
     
        if (component, error_code) in self.error_info.keys():
            self.error_info[(component, error_code)] += 1
        else:
            self.error_info[(component, error_code)] = 1

        if error_code == 0x25:
            # replace args of sixtop command/return code id by string
            arg1 = self.stack_defines["sixtop_returncodes"][arg1]
            arg2 = self.stack_defines["sixtop_states"][arg2]

        # turn into string
        output = "{MOTEID:x} [{COMPONENT}] [ASN={ASN}] {ERROR_DESC}".format(
            COMPONENT=self._translate_component(component),
            ASN=asn,
            MOTEID=mote_id,
            ERROR_DESC=self._translate_log_description(error_code, arg1, arg2),
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
