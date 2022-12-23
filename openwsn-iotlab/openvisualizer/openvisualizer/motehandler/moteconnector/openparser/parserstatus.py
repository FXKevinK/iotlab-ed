# Copyright (c) 2010-2013, Regents of the University of California.
# All rights reserved.
#
# Released under the BSD 3-Clause license as published at the link below.
# https://openwsn.atlassian.net/wiki/display/OW/License

import collections
import logging
import struct

from openvisualizer.motehandler.moteconnector.openparser import parser
from openvisualizer.motehandler.moteconnector.openparser.parserexception import ParserException
from openvisualizer.utils import format_buf

log = logging.getLogger('ParserStatus')
log.setLevel(logging.ERROR)
log.addHandler(logging.NullHandler())


class FieldParsingKey(object):

    def __init__(self, index, val, name, structure, fields):
        self.index = index
        self.val = val
        self.name = name
        self.structure = structure
        self.fields = fields


class ParserStatus(parser.Parser):
    HEADER_LENGTH = 4

    def __init__(self):

        # log
        log.debug("create instance")

        # initialize parent class
        super(ParserStatus, self).__init__(self.HEADER_LENGTH)

        # local variables
        self.fields_parsing_keys = []

        # register fields
        self._add_fields_parser(
            3,
            0,
            'IsSync',
            '<B',
            [
                'isSync',  # B
            ],
        )
        self._add_fields_parser(
            3,
            1,
            'IdManager',
            '<BBBBBBBBBBBBBBBBBBBBB',
            [
                'isDAGroot',  # B
                'myPANID_0',  # B
                'myPANID_1',  # B
                'my16bID_0',  # B
                'my16bID_1',  # B
                'my64bID_0',  # B
                'my64bID_1',  # B
                'my64bID_2',  # B
                'my64bID_3',  # B
                'my64bID_4',  # B
                'my64bID_5',  # B
                'my64bID_6',  # B
                'my64bID_7',  # B
                'myPrefix_0',  # B
                'myPrefix_1',  # B
                'myPrefix_2',  # B
                'myPrefix_3',  # B
                'myPrefix_4',  # B
                'myPrefix_5',  # B
                'myPrefix_6',  # B
                'myPrefix_7',  # B
            ],
        )
        self._add_fields_parser(
            3,
            2,
            'MyDagRank',
            '<H',
            [
                'myDAGrank',  # H
            ],
        )
        self._add_fields_parser(
            3,
            3,
            'OutputBuffer',
            '<HH',
            [
                'index_write',  # H
                'index_read',  # H
            ],
        )
        self._add_fields_parser(
            3,
            4,
            'Asn',
            '<BHH',
            [
                'asn_4',  # B
                'asn_2_3',  # H
                'asn_0_1',  # H
            ],
        )
        self._add_fields_parser(
            3,
            5,
            'MacStats',
            '<BBhhBII',
            [
                'numSyncPkt',  # B
                'numSyncAck',  # B
                'minCorrection',  # h
                'maxCorrection',  # h
                'numDeSync',  # B
                'numTicsOn',  # I
                'numTicsTotal',  # I
            ],
        )
        self._add_fields_parser(
            3,
            6,
            'ScheduleRow',
            '<BHBBBBBQQBQQBBBBBHH',
            [
                'row',  # B
                'slotOffset',  # H
                'type',  # B
                'shared',  # B
                'anycast', # B
                # 'isAutoCell',  # B
                'channelOffset',  # B
                'neighbor_type',  # B
                'neighbor_bodyH',  # Q
                'neighbor_bodyL',  # Q
                'neighbor2_type',  # B
                'neighbor2_bodyH',  # Q
                'neighbor2_bodyL',  # Q
                'numRx',  # B
                'numTx',  # B
                'numTxACK',  # B
                'priority', # B
                'lastUsedAsn_4',  # B
                'lastUsedAsn_2_3',  # H
                'lastUsedAsn_0_1',  # H
            ],
        )
        self._add_fields_parser(
            3,
            7,
            'Backoff',
            '<BB',
            [
                'backoffExponent',  # B
                'backoff',  # B
            ],
        )
        self._add_fields_parser(
            3,
            8,
            'QueueRow',
            '<BBBBQQBQQBBBBBBBBHH',  
            [
                'row', #B
                'creator',  # B
                'owner',  # B
                'l2addr_type',  # B
                'l2addr_bodyH',  # Q
                'l2addr_bodyL',  # Q
                'l3dest_type',  # B
                'l3dest_bodyH',  # Q
                'l3dest_bodyL',  # Q
                'length',  # B
                'l2_numTxAttempts', #B
                'l2_frameType', #B
                'l2_sixtop_messageType', #B
                'l2_sixtop_command', #B
                'l2_sixtop_returnCode', #B
                'l2_sixtop_cellOptions', #B
                'createdAsn_4',  # B
                'createdAsn_2_3',  # H
                'createdAsn_0_1',  # H
            ],
        )
        self._add_fields_parser(
            3,
            9,
            'NeighborsRow',
            '<BBBBBBBQQHbBBBBBHHBBBBB',
            [
                'row',  # B
                'used',  # B
                'insecure',  # B
                'parentPreference',  # B
                'stableNeighbor',  # B
                'switchStabilityCounter',  # B
                'addr_type',  # B
                'addr_bodyH',  # Q
                'addr_bodyL',  # Q
                'DAGrank',  # H
                'rssi',  # b
                'numRx',  # B
                'numTx',  # B
                'numTxACK',  # B
                'numWraps',  # B
                'asn_4',  # B
                'asn_2_3',  # H
                'asn_0_1',  # H
                'joinPrio',  # B
                'f6PNORES',  # B
                'sixtopSeqNum',  # B
                'backoffExponent',  # B
                'backoff',  # B
            ],
        )
        self._add_fields_parser(
            3,
            10,
            'kaPeriod',
            '<H',
            [
                'kaPeriod',  # H
            ],
        )
        self._add_fields_parser(
            3,
            11,
            'Joined',
            '<BHH',
            [
                'joinedAsn_4',  # B
                'joinedAsn_2_3',  # H
                'joinedAsn_0_1',  # H
            ],
        )
        self._add_fields_parser(
            3,
            12,
            'MSF',
            '<BB',
            [
                'numCellsUsed_tx',  # B
                'numCellsUsed_rx',  # B
            ],
        )

    # ======================== public ==========================================

    def parse_input(self, data):

        log.debug("received data={0}".format(data))
        
        # ensure data not short longer than header
        self._check_length(data)

        header_bytes = data[:3]

        # extract mote_id and status_elem
        try:
            (mote_id, status_elem) = struct.unpack('<HB', ''.join([chr(c) for c in header_bytes]))
        except struct.error:
            raise ParserException(ParserException.ExceptionType.DESERIALIZE.value,
                                  "could not extract moteId and statusElem from {0}".format(header_bytes))

        log.debug("moteId={0} statusElem={1}".format(mote_id, status_elem))

        # jump the header bytes
        data = data[3:]

        # call the next header parser
        for key in self.fields_parsing_keys:
            if status_elem == key.val:

                # log
                log.debug("parsing {0}, ({1} bytes) as {2}".format(data, len(data), key.name))

                # parse byte array
                try:
                    fields = struct.unpack(key.structure, ''.join([chr(c) for c in data]))
                except struct.error as err:
                    print(err)                    
                    raise ParserException(
                        ParserException.ExceptionType.DESERIALIZE.value,
                        "could not extract tuple {0} by applying {1} to {2}; error: {3}".format(
                            key.name,
                            key.structure,
                            format_buf(data),
                            str(err),
                        ),
                    )

                # map to name tuple
                return_tuple = self.named_tuple[key.name](*fields)

                # log
                log.debug("parsed into {0}".format(return_tuple))

                # map to name tuple
                return 'status', return_tuple

        # if you get here, no key was found
        raise ParserException(ParserException.ExceptionType.NO_KEY.value,
                              "type={0} (\"{1}\")".format(data[0], chr(data[0])))

    # ======================== private =========================================

    def _add_fields_parser(self, index=None, val=None, name=None, structure=None, fields=None):

        # add to fields parsing keys
        self.fields_parsing_keys.append(FieldParsingKey(index, val, name, structure, fields))

        # define named tuple
        self.named_tuple[name] = collections.namedtuple("Tuple_" + name, fields)
