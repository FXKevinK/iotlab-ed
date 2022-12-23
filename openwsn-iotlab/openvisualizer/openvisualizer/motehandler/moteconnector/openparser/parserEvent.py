# Copyright (c) 2017, CNRS.
# All rights reserved.
#
# Released under the BSD 3-Clause license as published at the link below.
# https://openwsn.atlassian.net/wiki/display/OW/License

import logging
import sys
import sqlite3
import traceback

import threading

from openvisualizer.motehandler.moteconnector.openparser import parser
from openvisualizer.motehandler.moteconnector.openparser.parserexception import ParserException
from openvisualizer.utils import format_buf


log = logging.getLogger('ParserEvent')
log.setLevel(logging.INFO)
log.addHandler(logging.NullHandler())


class ParserEvent(parser.Parser):
    HEADER_LENGTH = 2

    buffer = ""


    def __init__(self, mote_port):

        # log
        log.debug('create instance')
        
        # initialize parent class
        super(ParserEvent, self).__init__(self.HEADER_LENGTH)
       
       
        # create the db
        try:
            #one db per mote (for concurrent access)
            directory = os.path.dirname(log.handlers[0].baseFilename)
            self.dbfilename = directory+'/openv_events.' + mote_port + '.db'
        
            #flush the existing one + connection
            if (os.path.exists(self.dbfilename)):
                os.remove(self.dbfilename)
            dbconn = sqlite3.connect(self.dbfilename) # check_same_thread=False)
            dbconn.isolation_level = 'EXCLUSIVE'
            dbconn.execute('BEGIN EXCLUSIVE')
            log.success("created the sqlite db {}".format(self.dbfilename))


            # Create tables
            c = dbconn.cursor()
            #packet reception / transmission
            c.execute('''CREATE TABLE pkt
            (asn int, moteid text, event text, l2src text, l2dest text, type text, validrx int, slotOffset int, channelOffset int, shared int, autoCell int, priority int, numTxAttempts int, lqi int, rssi int, crc int, buffer_pos int)''')
           # c.execute('''CREATE TABLE pkt
           # (asn int, moteid text, event text, l2src text, l2dest text, type text, validrx int, slotOffset int, channelOffset int, shared int, autoCell int, priority int, numTxAttempts int, lqi int, rssi int, crc int, buffer_pos int, l3src text, l3dest text, l4proto int, l4destport int)''')

             #schedule modification
            c.execute('''CREATE TABLE schedule
            (asn int, moteid text, event text, neighbor text, neighbor2 text, type text, shared int, anycast int,  priority int, slotOffset int, channelOffset int)''')
            
            #RPL changes
            c.execute('''CREATE TABLE rpl
            (asn int, moteid text, event text, addr1 text, addr2 text)''')
            
           
            #SIXTOP
            c.execute('''CREATE TABLE sixtop
            (asn int, moteid text, seqNum int, event text, neighbor text, neighbor2 text,
            type int, command int, code int, numCells int)''')
            
            #SIXTOP STATE CHANGED
            c.execute('''CREATE TABLE sixtopStates
            (asn int, moteid text, state text)''')
                        
             #FRAME INTERRUPT
            c.execute('''CREATE TABLE frameInterrupt
            (asn int, moteid text, intrpt text, state text)''')
       
            #APPLICATION
            c.execute('''CREATE TABLE application
            (asn int, moteid text, component text, seqnum int, buffer_pos int)''')
            
            #QUEUE
            c.execute('''CREATE TABLE queue
            (asn int, moteid text, buffer_pos int, event text)''')

            #CONFIG EVENT
            c.execute('''CREATE TABLE config (asn int, moteid text, sixtop_timeout int, sixtop_anycast int, sixtop_lowest int, msf_numcells int, msf_maxcells int, msf_mincells int, neigh_maxrssi int, neigh_minrssi int, rpl_dagroot  int, debug_timing int, debug_rpl_enqueue int, debug_rank int, debug_sixtop int, debug_schedule int, debug_cca int, cexample_period int)''')
            
            dbconn.commit()
            dbconn.close()
            
            #to be initalized later for each thread
            self.dbconn = {}
            
        except AttributeError:
            log.error("ParserEvent: no LogHandler for parserEvent: we cannot store the events in a sqlite database")
        except:
            log.error("ParserEvent: Unexpected error for the database creation and connection:", sys.exc_info()[0])

        
         
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
        
    #mode to string
    @staticmethod
    def eventPktString(event):
        if (event == 1):
            return("RX")
        if (event == 2):
            return("TX")
        return("UNKNOWN")
    
    #type of packet to string
    @staticmethod
    def typePacketString(type):
        if (type == 0):
            return("BEACON")
        if (type == 1):
            return("DATA")
        if (type == 2):
            return("ACK")
        if (type == 3):
            return("CMD")
        if (type == 5):
            return("UNDEFINED")
        return("UNKNOWN")
        
     #type of event schedule modification to string
    @staticmethod
    def eventScheduleString(event):
        if (event == 1):
            return("ADD")
        if (event == 2):
            return("DEL")
            return("UNDEFINED")
        return(str(event))

    #type of cell to string
    @staticmethod
    def typeCellString(type):
        if (type == 0):
            return("OFF")
        if (type == 1):
            return("TX")
        if (type == 2):
            return("RX")
        if (type == 3):
            return("TXRX")
        return(str(type))
        
    #type of RPL event to string
    @staticmethod
    def eventRPLString(type):
        if (type == 1):
            return("PARENT_CHANGE")
        if (type == 2):
            return("SECONDPARENT_CHANGE")
        return(str(type))
                    
     #type of SIXTOP event to string
    @staticmethod
    def eventSixtopString(type):
        if (type == 1):
            return("SENDDONE")
        if (type == 2):
            return("REQ_CREATE")
        if (type == 3):
            return("RECEIVED")
        if (type == 4):
            return("SEQNUM_INCR")
        if (type == 5):
            return("SEQNUM_RESET")
        if (type == 6):
            return("CLEAR_BADPARENT")
        return(str(type))


    @staticmethod
    def typeSixtopString(type):
        if (type == 0):
            return("REQ")
        if (type == 1):
            return("REP")
        if (type == 2):
            return("CONF")
        if (type == 255):
            return("NONE")
        return(str(type))

    @staticmethod
    def codeSixtopString(code):
        if (code == 0):
            return("IANA_6TOP_RC_SUCCESS")
        if (code == 1):
            return("IANA_6TOP_RC_EOL")
        if (code == 2):
            return("IANA_6TOP_RC_ERROR")
        if (code == 3):
            return("IANA_6TOP_RC_RESET")
        if (code == 4):
            return("IANA_6TOP_RC_VER_ERR")
        if (code == 5):
            return("IANA_6TOP_RC_SFID_ERR")
        if (code == 6):
            return("IANA_6TOP_RC_SEQNUM_ERR")
        if (code == 7):
            return("IANA_6TOP_RC_CELLLIST_ERR")
        if (code == 8):
            return("IANA_6TOP_RC_BUSY")
        if (code == 9):
            return("IANA_6TOP_RC_LOCKED")
        if (code == 255):
            return("NONE")
        return(str(code))

    @staticmethod
    def commandSixtopString(code):
        if (code == 0):
            return("IANA_6TOP_CMD_NONE")
        if (code == 1):
            return("IANA_6TOP_CMD_ADD")
        if (code == 2):
            return("IANA_6TOP_CMD_DELETE")
        if (code == 3):
            return("IANA_6TOP_CMD_RELOCATE")
        if (code == 4):
            return("IANA_6TOP_CMD_COUNT")
        if (code == 5):
            return("IANA_6TOP_CMD_LIST")
        if (code == 6):
            return("IANA_6TOP_CMD_SIGNAL")
        if (code == 7):
            return("IANA_6TOP_CMD_CLEAR")
        if (code == 255):
            return("NONE")
        return(str(code))
        
    @staticmethod
    def sixtopStateString(code):
        if (code == 0):
            return("IDLE")
        if (code == 1):
            return("WAIT_ADDREQUEST_SENDDONE")
        if (code == 2):
            return("WAIT_DELETEREQUEST_SENDDONE")
        if (code == 3):
            return("WAIT_RELOCATEREQUEST_SENDDONE")
        if (code == 4):
            return("WAIT_COUNTREQUEST_SENDDONE")
        if (code == 5):
            return("WAIT_LISTREQUEST_SENDDONE")
        if (code == 6):
            return("WAIT_CLEARREQUEST_SENDDONE")
        if (code == 7):
            return("WAIT_ADDRESPONSE")
        if (code == 8):
            return("WAIT_DELETERESPONSE")
        if (code == 9):
            return("WAIT_RELOCATERESPONSE")
        if (code == 10):
            return("WAIT_COUNTRESPONSE")
        if (code == 11):
            return("WAIT_LISTRESPONSE")
        if (code == 12):
            return("WAIT_CLEARRESPONSE")
        if (code == 13):
            return("WAIT_ADDREQUEST")
        if (code == 255):
            return("NONE")
        return(str(code))
        
    @staticmethod
    def frameInterruptString(code):
        if (code == 0):
            return("STARTOFFRAME")
        if (code == 1):
            return("ENDOFFRAME")
        if (code == 2):
            return("CCA_IDLE")
        if (code == 3):
            return("CCA_BUSY")
        return(str(code))

    @staticmethod
    def ieee154eStateString(code):
        if (code == 0):
            return("S_SLEEP")
        if (code == 1):
            return("S_SYNCLISTEN")
        if (code == 2):
            return("S_SYNCRX")
        if (code == 3):
            return("S_SYNCPROC")
        if (code == 4):
            return("S_TXDATAOFFSET")
        if (code == 5):
            return("S_TXDATAPREPARE")
        if (code == 6):
            return("S_TXDATAREADY")
        if (code == 7):
            return("S_TXDATADELAY")
        if (code == 8):
            return("S_TXDATA")
        if (code == 9):
            return("S_RXACKOFFSET")
        if (code == 10):
            return("S_RXACKPREPARE")
        if (code == 11):
            return("S_RXACKREADY")
        if (code == 12):
            return("S_RXACKLISTEN")
        if (code == 13):
            return("S_RXACK")
        if (code == 14):
            return("S_TXPROC")
        if (code == 15):
            return("S_RXDATAOFFSET")
        if (code == 16):
            return("S_RXDATAPREPARE")
        if (code == 17):
            return("S_RXDATAREADY")
        if (code == 18):
            return("S_RXDATALISTEN")
        if (code == 19):
            return("S_RXDATA")
        if (code == 20):
            return("S_TXACKOFFSET")
        if (code == 21):
            return("S_TXACKPREPARE")
        if (code == 22):
            return("S_TXACKREADY")
        if (code == 23):
            return("S_TXACKDELAY")
        if (code == 24):
            return("S_TXACK")
        if (code == 25):
            return("S_RXPROC")
        if (code == 26):
            return("S_CCATRIGGER")
        if (code == 27):
            return("S_CCATRIGGERED")
        if (code == 255):
            return("NONE")
        return(str(code))
     
    @staticmethod
    def componentString(code):
         if (code == 0x00):
            return("NULL")
         if (code == 0x01):
            return("OPENWSN")
         if (code == 0x02):
            return("IDMANAGER")
         if (code == 0x03):
            return("OPENQUEUE")
         if (code == 0x04):
            return("OPENSERIAL")
         if (code == 0x05):
            return("PACKETFUNCTIONS")
         if (code == 0x06):
            return("RANDOM")
         if (code == 0x07):
            return("RADIO")
         if (code == 0x08):
            return("IEEE802154")
         if (code == 0x09):
            return("IEEE802154E")
         if (code == 0x0a):
            return("SIXTOP_TO_IEEE802154E")
         if (code == 0x0b):
            return("IEEE802154E_TO_SIXTOP")
         if (code == 0x0c):
            return("SIXTOP")
         if (code == 0x0d):
            return("NEIGHBORS")
         if (code == 0x0e):
            return("SCHEDULE")
         if (code == 0x0f):
            return("SIXTOP_RES")
         if (code == 0x10):
            return("MSF")
         if (code == 0x11):
            return("OPENBRIDGE")
         if (code == 0x12):
            return("IPHC")
         if (code == 0x13):
            return("FRAG")
         if (code == 0x14):
            return("FORWARDING")
         if (code == 0x15):
            return("OPENBRIDGE")
         if (code == 0x16):
            return("ICMPv6ECHO")
         if (code == 0x17):
            return("ICMPv6ROUTER")
         if (code == 0x18):
            return("ICMPv6RPL")
         if (code == 0x19):
            return("UDP")
         if (code == 0x1a):
            return("SOCK_TO_UDP")
         if (code == 0x1b):
            return("UDP_TO_SOCK")
         if (code == 0x1c):
            return("OPENCOAP")
         if (code == 0x1d):
            return("CJOIN")
         if (code == 0x1e):
            return("OSCORE")
         if (code == 0x1f):
            return("C6T")
         if (code == 0x20):
            return("CEXAMPLE")
         if (code == 0x21):
            return("CINFO")
         if (code == 0x22):
            return("CLEDS")
         if (code == 0x23):
            return("CSENSORS")
         if (code == 0x24):
            return("CSTORM")
         if (code == 0x25):
            return("CSENSORS")
         if (code == 0x26):
            return("UECHO")
         if (code == 0x27):
            return("UINJECT")
         if (code == 0x28):
            return("RRT")
         if (code == 0x29):
            return("SECURITY")
         if (code == 0x2a):
            return("USERIALBRIDGE")
         if (code == 0x2b):
            return("UEXPIRATION")
         if (code == 0x2c):
            return("UMONITOR")
         if (code == 0x2d):
            return("CINFRARED")
        
        
    @staticmethod
    def queueEventString(code):
        if (code == 1):
            return("ALLOCATE")
        if (code == 2):
            return("DELETE")
        return(str(code))
        
    #return a connection to the DB for this thread
    def get_dbconn(self):
        threadname = threading.current_thread().name
        
        #creates the connection for this thread if none exists
        if self.dbconn.has_key(threadname) is False:
            dbconn = sqlite3.connect(self.dbfilename)
            dbconn.isolation_level = 'EXCLUSIVE'
            dbconn.execute('BEGIN EXCLUSIVE')
            self.dbconn[threadname]  = dbconn
            
            log.success("connection to sqlite db {}, threadname {}".format(self.dbfilename, threadname))

        
        return(self.dbconn[threadname])
           
       
    def parse_input(self, data):

        # log
        log.debug('received stat {0}'.format(data))
        
        #incorrect length
        if (len(data) < 14):
            log.error("ParserEvent: Invalid length for this event: {0}<14", len(data))
            return
        
        asn = ParserEvent.bytes_to_string(data[0:5])    # asn
        typeStat = data[5]
        moteid   = ParserEvent.bytes_to_addr(data[6:14])                           # type
        
        
        try:
            #handle each statistic independently
            #PKT TRANSMISSION / RECEPTION
            if (typeStat == 1):
                if (len(data) != 43):
                    log.error("ParserEvent: Incorrect length for a stat_pkt in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data
               
            

                event           = ParserEvent.eventPktString(data[14])
                l2src           = ParserEvent.bytes_to_addr(data[15:23])
                l2dest          = ParserEvent.bytes_to_addr(data[23:31])
                validRx         = data[31]
                type            = ParserEvent.typePacketString(data[32])
                slotOffset      = data[33]
                channelOffset   = data[34]
                shared          = data[35]
                isAutoCell      = data[36]
                priority        = data[37]
                numTxAttempts   = data[38]
                lqi             = data[39]
                rssi            = data[40]
                crc             = data[41]
                buffer_pos      = data[42]
               # l3src           = ParserEvent.bytes_to_addr(data[43:59])
               # l3dest          = ParserEvent.bytes_to_addr(data[59:75])
               # l4proto         = data[75]
               # l4destport      = data[76] + 256 * data[77]
                
                
                
                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                #c.execute("""INSERT INTO pkt (asn,moteid,event,l2src,l2dest,type,validrx, slotOffset,channelOffset,shared,autoCell, priority,numTxAttempts,lqi,rssi,crc,buffer_pos,l3src,l3dest,l4proto,l4destport) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (asn, moteid, event, l2src, l2dest, type, validRx, slotOffset, channelOffset, shared, isAutoCell, priority, numTxAttempts, lqi, rssi, crc, buffer_pos,l3src,l3dest,l4proto,l4destport))
                c.execute("""INSERT INTO pkt (asn,moteid,event,l2src,l2dest,type,validrx, slotOffset,channelOffset,shared,autoCell, priority,numTxAttempts,lqi,rssi,crc,buffer_pos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (asn, moteid, event, l2src, l2dest, type, validRx, slotOffset, channelOffset, shared, isAutoCell, priority, numTxAttempts, lqi, rssi, crc, buffer_pos))
                dbconn.commit()

             
            #SCHEDULE
            elif (typeStat == 2):
                if (len(data) != 37):
                    log.error("ParserEvent: Incorrect length for a stat_schedule in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data
            
                event           = ParserEvent.eventScheduleString(data[14])
                neighbor        = ParserEvent.bytes_to_addr(data[15:23])
                neighbor2       = ParserEvent.bytes_to_addr(data[23:31])
                type            = ParserEvent.typeCellString(data[31])
                shared          = data[32]
                anycast         = data[33]
                priority        = data[34]
                slotOffset      = data[35]
                channelOffset   = data[36]
                

                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO schedule (asn, moteid, event, neighbor, neighbor2, type, shared, anycast, priority, slotOffset,channelOffset) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (asn, moteid, event, neighbor, neighbor2, type, shared, anycast, priority, slotOffset, channelOffset))
                dbconn.commit()
    
                
            #RPL
            elif (typeStat == 3):
                if (len(data) != 31):
                    log.error("ParserEvent: Incorrect length for a stat_rpl in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data
            
                event           = ParserEvent.eventRPLString(data[14])
                addr1           = ParserEvent.bytes_to_addr(data[15:23])
                addr2           = ParserEvent.bytes_to_addr(data[23:31])

                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO rpl (asn, moteid, event, addr1, addr2) VALUES (?,?,?,?,?)""", (asn, moteid, event, addr1, addr2))
                dbconn.commit()
                    
            #SIXTOP
            elif (typeStat == 4):
                if (len(data) != 36):
                    log.error("ParserEvent: Incorrect length for a stat_sixtop in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data

                event           = ParserEvent.eventSixtopString(data[14])
                neighbor        = ParserEvent.bytes_to_addr(data[15:23])
                neighbor2       = ParserEvent.bytes_to_addr(data[23:31])
                type            = ParserEvent.typeSixtopString(data[31])
                code            = ParserEvent.codeSixtopString(data[32])
                command         = ParserEvent.commandSixtopString(data[33])
                seqNum          = data[34]
                numCells        = data[35]
                
                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO sixtop (asn, moteid, event, neighbor, neighbor2, type, code, command, seqNum, numCells) VALUES (?,?,?,?,?,?,?,?,?,?)""", (asn, moteid, event, neighbor, neighbor2, type, code, command, seqNum, numCells))
                dbconn.commit()

            #SIXTOP STATE CHANGED
            elif (typeStat == 5):
                if (len(data) != 15):
                    log.error("ParserEvent: Incorrect length for a stat_sixtopchangeState in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data

                state           = ParserEvent.sixtopStateString(data[14])
                
                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO sixtopStates (asn, moteid, state) VALUES (?,?,?)""", (asn, moteid, state))
                dbconn.commit()
     
                    
            #SIXTOP STATE CHANGED
            elif (typeStat == 6):
                if (len(data) != 16):
                    log.error("ParserEvent: Incorrect length for a frameInterrupt in ParserEvent.py ({0})".format(len(data)))
                    return 'error', data

                intrpt = ParserEvent.frameInterruptString(data[14])
                state  = ParserEvent.ieee154eStateString(data[15])

                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO frameInterrupt (asn, moteid, intrpt, state) VALUES (?,?,?,?)""", (asn, moteid, intrpt, state))
                dbconn.commit()
  
            #APPLICATION
            elif (typeStat == 7):
                if (len(data) != 18):
                    log.error("ParserEvent: Incorrect length for an application in ParserEvent.py (length={0},data={1})".format(len(data), data))
                    return 'error', data

                component = ParserEvent.componentString(data[14])
                seqnum  = data[15] + 256 * data[16]
                buffer_pos = data[17]
                
                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO application (asn, moteid, component, seqnum, buffer_pos) VALUES (?,?,?,?,?)""", (asn, moteid, component, seqnum, buffer_pos))
                dbconn.commit()
   
            #OPENQUEUE
            elif (typeStat == 8):
                if (len(data) != 16):
                    log.error("ParserEvent: Incorrect length for a queue in ParserEvent.py (length={0},data={1})".format(len(data), data))
                    return 'error', data

                buffer_pos = data[14]
                event  = ParserEvent.queueEventString(data[15])

                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO queue (asn, moteid, buffer_pos, event) VALUES (?,?,?,?)""", (asn, moteid, buffer_pos, event))
                dbconn.commit()
               
            #CONFIG
            elif (typeStat == 9):
                if (len(data) != 32):
                    log.error("ParserEvent: Incorrect length for a config in ParserEvent.py (length={0},data={1})".format(len(data), data))
                    return 'error', data

                
                #sixtop
                sixtop_timeout = data[14] + 256 * data[15]
                sixtop_anycast = data[16]
                sixtop_lowest  = data[17]
                #msf
                msf_numcells    = data[18]
                msf_maxcells    = data[19]
                msf_mincells    = data[20]
                #neighborhood table
                neigh_maxrssi   = data[21]
                neigh_minrssi   = data[22]
                #rpl
                rpl_dagroot     = data[23]
                #debug
                debug_timing    = data[24]
                debug_rpl_enqueue = data[25]
                debug_rank      = data[26]
                debug_sixtop    = data[27]
                debug_schedule  = data[28]
                debug_cca       = data[29]
                #app
                cexample_period = data[30] + 256 * data[31]
                
                dbconn = self.get_dbconn()
                c = dbconn.cursor()
                c.execute("""INSERT INTO config (asn, moteid, sixtop_timeout, sixtop_anycast, sixtop_lowest, msf_numcells, msf_maxcells, msf_mincells, neigh_maxrssi, neigh_minrssi, rpl_dagroot , debug_timing, debug_rpl_enqueue, debug_rank, debug_sixtop, debug_schedule, debug_cca, cexample_period) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (asn, moteid, sixtop_timeout, sixtop_anycast, sixtop_lowest, msf_numcells, msf_maxcells, msf_mincells, neigh_maxrssi, neigh_minrssi, rpl_dagroot , debug_timing, debug_rpl_enqueue, debug_rank, debug_sixtop, debug_schedule, debug_cca, cexample_period))
                dbconn.commit()
                    
   
            else:
                log.error('ParserEvent: unknown statistic type={0}'.format(typeStat))
               
        except sqlite3.OperationalError as e:
            log.error("ParserEvent: Database error: {}".format(e))
            log.error(e.args)
        except  Exception as e:
            log.error("ParserEvent: Database unexpected error:")
            traceback.print_exc()

            
            
        #sys.stdout.write("{0} {1} ".format(mote_id, asn));
        #sys.stdout.write("{}".format("".join([chr(c) for c in data[7:]])))
        #sys.stdout.flush()
          
       
        
        # everything was fine
        return 'error', data

