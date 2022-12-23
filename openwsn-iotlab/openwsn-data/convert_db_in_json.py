#!/usr/bin/env python
# coding: utf-8

# systems tools
import os
import shutil
import sys
import time
import sys
import signal
import random

# multiprocess
import threading
import psutil

#format
import string
import json

#sqlite
import sqlite3

#args
import argparse

#maths
import numpy as np

#strings
import re   #regular expressions

#FIFO
from collections import deque

#pandas
import pandas as pd
from IPython.display import display



#Constants
DEBUG = True
DB_FILENAME = "openv_events.db"
JSON_FILENAME = "stats.json"
TABLES_NAME = ['application', 'config', 'frameInterrupt', 'pkt', 'queue', 'rpl', 'schedule', 'sixtop', 'sixtopStates' ]




#initialization: args + sqlite connection
def init():
    #parsing arguments
    parser = argparse.ArgumentParser(description='data processing from a sqlite openwsn db.')

    parser.add_argument('--dir',
                        default="./results",
                        help='directory to parse (one directory per experiment)')

    parser.add_argument('--rewrite', dest='rewrite', action='store_true',
                            help='rewrite the stats even if a json file exists in a subdirectory')
    parser.add_argument('--no-rewrite', dest='rewrite', action='store_false',
                            help='keep the stats if a json file exists in a subdirectory')
    parser.set_defaults(rewrite=False)

    args = parser.parse_args()
    print("DIR:{}".format(args.dir))
    print("REWRITE:{}".format(args.rewrite))
   
    
    return(args)



#retrives the table names
def loadTables(file_out, file_in):
    db_out = sqlite3.connect(file_out)
    db_in = sqlite3.connect(file_in)

    tables_in = []
    cursor_in = db_in.cursor()
    for row in cursor_in.execute("SELECT name FROM sqlite_master WHERE type='table';"):
        tables_in.append(row[0])
        
    tables_out = []
    cursor_out = db_out.cursor()
    for row in cursor_out.execute("SELECT name FROM sqlite_master WHERE type='table';"):
        tables_out.append(row[0])
            
    
    return db_out, db_in, tables_out, tables_in



#merge 'in' into 'out'
def merge(db_out, db_in, tables_out, tables_in):
    cursor_in = db_in.cursor()
    cursor_out = db_out.cursor()

    for id_, name, filename in db_in.execute('PRAGMA database_list'):
        if name == 'main' and filename is not None:
            print("Merging tables for db {}: ".format(os.path.basename(filename)), end = '')
            break
     
    #for each table
    for table_name in tables_in:

        #one exists -> copy of in + out in a tmp table + removal + renaming
        if table_name in tables_out:
            new_table_name = table_name + "_tmp"
            try:
                #copy of the table in out
                cursor_out.execute("CREATE TABLE IF NOT EXISTS " + new_table_name + " AS SELECT * FROM " + table_name)
                
                #copy of in into out
                for row in cursor_in.execute("SELECT * FROM " + table_name):
                    #print(row)
                    cursor_out.execute("INSERT INTO " + new_table_name + " VALUES" + str(row) +";")

                #rename the table with the right name
                cursor_out.execute("DROP TABLE IF EXISTS " + table_name);
                cursor_out.execute("ALTER TABLE " + new_table_name + " RENAME TO " + table_name);

            except sqlite3.OperationalError:
                print("ERROR!: Merge Failed")
                cursor_out.execute("DROP TABLE IF EXISTS " + new_table_name);


        #no table exists -> creation of the schema AND copy
        else:
            for sql in cursor_in.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='"+ table_name +"'"):
                cursor_out.execute(sql[0])
        
            for row in cursor_in.execute("SELECT * FROM " + table_name):
                #print(row)
                cursor_out.execute("INSERT INTO " + table_name + " VALUES" + str(row) +";")

        
        db_out.commit()
        #print("{} ".format(table_name), end = '')

    print(".. ok")
    db_in.close()
    db_out.close()

    return



#returns a connection to the global sqlite db
def dbconn_aggregate_get(directory):
    db_filename_out = os.path.join(directory, DB_FILENAME)
    
    #flush existing db file + connection
    if os.path.isfile(db_filename_out) is True:
        os.remove(db_filename_out)
    dbconn = sqlite3.connect(db_filename_out)
    return(dbconn)
  
  

#merge the indidivudal sqlite dbs in a single one
def merge_sqllite_db(directory):
    dbconn = None
    
    db_filename_out = os.path.join(directory, DB_FILENAME)
    


    #for all db files
    for (dirpath, dirnames, db_filenames_in) in os.walk(directory):
        for db_filename_in in db_filenames_in:
            
            #db extension + emulated/m3 portname before a digit
            if re.search("((emulated[0-9]+)|(m3-[0-9]+.*)).db$", db_filename_in) is not None:
            
                #emptydbconn
                if dbconn is None:
                    dbconn = dbconn_aggregate_get(directory)
                    
                  

            
                db_out, db_in, tables_out, tables_in = loadTables(db_filename_out, os.path.join(directory, db_filename_in))
                merge(db_out, db_in, tables_out, tables_in)
            
            
             
             
    if dbconn is not None:
        dbconn.close()
                
                

        



#multithreading is here safe because we NEVER modify the db, we just read it
def db_create_connection(db_filename):
    return(sqlite3.connect(db_filename, check_same_thread=False))


#returns the list of motes
def motes_get(con):
    motes = []
    cur = con.cursor()
    for row in cur.execute('SELECT DISTINCT moteid FROM sixtopStates'):
        motes.append(row[0])
    return(motes)


#returns the list of dagroot ids
def dagroot_ids_get(con):
    dagroot_ids = []
    cur = con.cursor()
    for row in cur.execute('SELECT DISTINCT moteid FROM config WHERE rpl_dagroot="1"'):
        dagroot_ids.append(row[0])
    return(dagroot_ids)

#returns the configuration
def configuration_get(con):
    config = {}
    cur = con.cursor()
    for row in cur.execute('SELECT DISTINCT sixtop_anycast, sixtop_lowest, msf_numcells, msf_maxcells, msf_mincells, neigh_maxrssi, neigh_minrssi, cexample_period  FROM config'):
        
        config['sixtop_anycast'] = row[0]
        config['sixtop_lowest'] = row[1]
        config['msf_numcells'] = row[2]
        config['msf_maxcells'] = row[3]
        config['msf_mincells'] = row[4]
        config['neigh_maxrssi'] = row[5]
        config['neigh_minrssi'] = row[6]
        config['cexample_period'] = row[7]

        return(config)
    return(None)
    
    


#returns the largest ASN in the experiment
def asn_end_get(con):
    cur = con.cursor()
    for row in cur.execute('SELECT MAX(asn) as max FROM queue'):
        return(row[0])
    return(0)




#returns the list of links (anycast = yes / no) + the tx/rx
def links_get(con):
    links = []
    cur = con.cursor()
    for row in cur.execute('SELECT DISTINCT moteid, neighbor, neighbor2, anycast, asn, slotOffset, channelOffset  FROM schedule WHERE type="TX" AND shared="0" AND event="ADD"'):
        
        #search for the correspond DEL asn
        cur2 = con.cursor()
        asn_end = None
       
        
        
        for row2 in cur2.execute('SELECT asn  FROM schedule WHERE type="TX" AND shared="0" AND event="DEL" AND moteid="{0}" AND neighbor="{1}" AND slotOffset="{2}" '.format(row[0], row[1], row[5])):
             
            #keep the smallest ASN larger than the start_asn
            if row2[0] > row[4] and ( asn_end is None or row2[0] < asn_end):
                asn_end = row2[0]
            
        links.append({'src':row[0], 'neigh':row[1], 'neigh2':row[2], 'anycast':row[3], 'slot':row[5], 'channel':row[6], 'start':row[4], 'end':asn_end})
        
    return(links)


#all l2 data tx
def l2tx_get(con):
    l2tx = []
    
    cur = con.cursor()

   
    sql_request = 'SELECT dataTX.asn, dataTX.moteid, dataTX.l2dest, dataTX.slotOffset, dataTX.channelOffset, dataTX.shared, dataTX.autoCell, dataTX.buffer_pos, \
    dataRX.moteid, dataRX.priority, dataRX.crc, dataRx.rssi, dataRx.buffer_pos,  \
    ackTX.moteid, \
    ackRX.crc, \
    INTRPT.intrpt\
    FROM pkt AS dataTX\
    LEFT JOIN(\
        SELECT *\
        FROM pkt\
        WHERE type="DATA" AND event="RX"\
    ) dataRX\
    ON dataTX.moteid=dataRX.l2src AND dataTX.asn=dataRX.asn\
    LEFT JOIN (\
        SELECT *\
        FROM pkt \
        WHERE type="ACK" AND event="TX"\
    ) ackTX\
    ON ackTX.moteid = dataRX.moteid AND ackTX.asn=dataRX.asn\
    LEFT JOIN(\
        SELECT *\
        FROM pkt \
        WHERE type="ACK" AND event="RX"\
    ) ackRX\
    ON ackTX.moteid = ackRX.l2src AND ackTX.asn=ackRX.asn\
    LEFT JOIN(\
        SELECT *\
        FROM frameInterrupt\
        WHERE (intrpt="STARTOFFRAME" AND state="S_CCATRIGGER") OR (intrpt="CCA_IDLE" AND state="S_CCATRIGGERED")\
    )INTRPT\
    ON INTRPT.asn=dataRX.asn AND INTRPT.moteid=dataRX.moteid\
    WHERE dataTX.type="DATA" AND dataTX.event="TX" '



    #print(sql_request)
    
    for row in cur.execute(sql_request):
        
        l2tx.append({'asn': row[0], 'moteid_tx':row[1], 'moteid_dest':row[2], 'slotOffset':row[3], 'channelOffset':row[4], 'shared':row[5], 'autoCell':row[6], 'tx_buffer_pos':row[7], 'moteid_rx':row[8],  'priority_rx':row[9], 'crc_data':row[10], 'rssi':row[11], 'rx_buffer_pos':row[12], 'ack_tx':(row[13] is not None), 'crc_ack':row[14], 'intrpt':row[15]})
     
  
    return(l2tx)
        

            
##returns the list of receivers for this l2 transmission
def cex_l2receivers_get(con, l2src, asn):

    receivers = []
    cur_rx = con.cursor()
    for rx in cur_rx.execute('SELECT moteid, buffer_pos, crc, rssi, priority FROM pkt WHERE event="RX" AND type="DATA" AND asn="{0}" AND l2src="{1}"'.format(asn, l2src)):
        if DEBUG:
            print("   rx(anycast, {1}): {0}".format(rx, l2src))
        moteid      = rx[0]
        buffer_pos  = rx[1]
        crc         = rx[2]
        rssi        = rx[3]
        priority    = rx[4]
        
        #if the packet has been received correctly, track the corresponding ack tx
        ack_txed = 0
        if (crc == 1):
            cur_acktx = con.cursor()
            cur_acktx.execute('SELECT moteid FROM pkt WHERE event="TX" AND type="ACK" AND asn="{0}" AND l2src="{1}"'.format(asn, rx[0]))
            results = cur_acktx.fetchall()
            
            
            
            #an ack has been txed -> it will try to forward the packet
            if (len(results) == 0):     # probably second receiver in anycast
                ack_txed = 0
            
            elif (len(results) == 1):       #an ack has been txed
                ack_txed = 1
                 
            elif DEBUG:
                print("Hum, several acks from the same moteid? sounds strange....")
                print(results)
                print('SELECT moteid FROM pkt WHERE event="TX" AND type="ACK" AND asn="{0}" AND l2src="{1}"'.format(asn, rx[0]))
        else:
            print("BAD CRC, not POPPED")
         
        #insert this receiver for this hop
        receivers.append({'moteid':moteid, 'crc':crc, 'rssi':rssi, 'buffer_pos':buffer_pos, 'priority':priority, 'ack_txed':ack_txed})
        
    return(receivers)
   


#list all the l2 transmissions for a given mote (packet in the queue of a mote)
#be careful: a mote may receive the same cex_packet several times, each will constitute a different "hop"
def cex_l2transmissions_for_hop(con, l2tx_list, processingQueue, elem):
    
    #for each TX *and* RETX in this two-ASN interval
    cur_tx = con.cursor()
    for tx in cur_tx.execute('SELECT asn, slotOffset, channelOffset, l2dest FROM pkt WHERE moteid="{0}" AND event="TX" AND type="DATA" AND buffer_pos="{1}" AND asn<="{2}" AND asn>="{3}" '.format(elem['l2src'], elem['buffer_pos'], elem['asn_del'], elem['asn_add'])):
        asn             = tx[0]
        slotOffset      = tx[1]
        channelOffset   = tx[2]
        l2dest          = tx[3]
        #print("txdata: src={1} & asn={0}".format(asn, elem['l2src']))

        #an ack has been correctly received? (crc ok)
        cur_rxack = con.cursor()
        ack_rcvd = 0
        cur_rxack.execute('SELECT moteid, buffer_pos FROM pkt WHERE event="RX" AND type="ACK" AND asn="{0}" AND crc="1" '.format(asn))
        results = cur_rxack.fetchall()
        if (len(results) > 0):
            ack_rcvd = 1

        #list the l2 receivers for this l2 transmission
        receivers = cex_l2receivers_get(con, elem['l2src'], asn)
        
        #add the receivers to the processing list (if it sent an ack, it means it will forward the packet)
        for rcvr in receivers:
            if rcvr['ack_txed'] == 1:
                if (DEBUG):
                    print("TO PROCESS: id={0}, asn={1}, buffer_pos={2}".format(rcvr['moteid'], asn, rcvr['buffer_pos']))
                processingQueue.append({'l2src':rcvr['moteid'], 'buffer_pos':rcvr['buffer_pos'], 'asn_add':asn})
                
           
        #we have listed everything for this hop
        l2tx_list.append({'asn':tx[0], 'l2src':elem['l2src'], 'buffer_pos':elem['buffer_pos'], 'slotOffset':slotOffset, 'channelOffset':channelOffset, 'l2dest':l2dest, 'ack_rcvd':ack_rcvd,  'receivers':receivers })
        
        if DEBUG:
            print("")
            print("")
 
                   
#list all the l2 transmissions for a given mote (packet in the queue of a mote)
#be careful: a mote may receive the same cex_packet several times, each will constitute a different "hop"
def cex_l2transmissions_for_cex_packet(con, cex_packet, dagroot_ids, moteid, buffer_pos, asn_gen, l2tx_pd):

    l2tx_list = []
    cur_queue = con.cursor()

    #list of motes (to be processed) which recived (and will forward) the packet
    processingQueue = deque()
    processingQueue.append({'l2src':moteid, 'buffer_pos':buffer_pos, 'asn_add':asn_gen})
  
    # do until there is no hop to explore
    try:
        while True:
            hop_current = processingQueue.popleft()

            if cex_packet['cex_src'] == '44054332ff03dab369':
                DEBUG = True
                print("")
                print("--------------------------")
                print("")
                print("")
            else:
                DEBUG = False



            #ASN of deletion
            sql_query = 'SELECT asn FROM queue WHERE moteid="{0}" AND asn>="{1}" AND event="DELETE" AND buffer_pos="{2}" ORDER BY asn ASC '.format(hop_current['l2src'], hop_current['asn_add'], int(hop_current['buffer_pos']))
            if DEBUG:
                print("{} seqnum={} asn={}".format(cex_packet['cex_src'], cex_packet['seqnum'], cex_packet['asn'])   )
                print(sql_query)
            cur_queue.execute(sql_query)

            #no result -> the packet has not been txed / dropped -> discard it
            results = cur_queue.fetchall()
            if (len(results) == 0):
                if DEBUG:
                    print("no result")
                break
            hop_current['asn_del'] = results[0][0]

            #impossible to TX and RX the same packet in the same slot -> BUG
            #TODO
            if False and hop_current['asn_del'] == hop_current['asn_add'] and hop_current['l2src'] not in dagroot_ids:
                print("BUG: We cannot have a data packet received and transmitted in the same slot. We have a bug somewhere")
                print(hop_current)
                sys.exit(2)
            
            if DEBUG:
                print("      del= {}".format(results[0][0]))
                print("      bufferpos={}, l2src={}".format(hop_current['buffer_pos'], hop_current['l2src']))

        

            receivers = []
            #get all the packets txed by this mote during this time interval
            list_pd = l2tx_pd[
                (l2tx_pd['asn'] >= hop_current['asn_add']) &
                (l2tx_pd['asn'] <= hop_current['asn_del']) &
                (l2tx_pd['tx_buffer_pos'] == hop_current['buffer_pos']) &
                (l2tx_pd['moteid_tx'] == hop_current['l2src'])
                ]
            
        
            #group by asn (make a distinction between the different retx
            list_pd = list_pd.groupby('asn')
            
            if DEBUG :
                display(list_pd)

            #for each specific timeslot
            for df_name, df_group in list_pd:
            
                #by default ack not received
                ack_rcvd = False
            
                #for each receiver for this timeslot
                for row_index, row in df_group.iterrows():
                    if DEBUG:
                        display(row)
                    
                    if row['moteid_rx'] is not None:
                        #did it tx an ack ?
                        if row['ack_tx']:
                            processingQueue.append({'l2src':row['moteid_rx'], 'buffer_pos':row['rx_buffer_pos'], 'asn_add':row['asn']})
                            
                        #did the tx receive the ack?
                        if row['crc_ack']:
                            ack_rcvd = True
                            
                        receivers.append({
                        'moteid':row['moteid_rx'],
                        'crc':int(row['crc_data']),
                        'rssi':int(row['rssi']),
                        'buffer_pos':int(row['rx_buffer_pos']),
                        'priority':int(row['priority_rx']),
                        'ack_txed':row['ack_tx']
                        })
                        
                #we have listed everything for this hop
                l2tx_list.append({
                'asn':int(df_name),
                'l2src':hop_current['l2src'],
                'buffer_pos':int(hop_current['buffer_pos']),
                'slotOffset':int(df_group.iloc[0]['slotOffset']),
                'channelOffset':int(df_group.iloc[0]['channelOffset']),
                'l2dest':df_group.iloc[0]['moteid_dest'],
                'ack_rcvd':ack_rcvd,
                'receivers':receivers
                })
    #the queue is empty
    except IndexError:
        pass
    except Exception as e:
        print(e)
        
            
        
    
    #display(list_pd)
    #print("-------")


    return(l2tx_list)



        
#returns the list of cexample packets, and each corresponding l2 transmission
def cex_packets_end2end(con, dagroot_ids, l2tx_pd):
    cex_packets_stats = []
    
    #handles each cexample packet
    cur_cexample = con.cursor()
    for packet in cur_cexample.execute('\
        SELECT cexample.moteid, cexample.seqnum, cexample.asn, sockudp.buffer_pos \
        FROM application AS cexample \
        INNER JOIN(\
            SELECT *\
            FROM application\
            WHERE component="SOCK_TO_UDP"\
    )sockudp \
    ON sockudp.asn=cexample.asn AND cexample.moteid=sockudp.moteid \
    WHERE cexample.component="CEXAMPLE" \
    '):
        moteid      = packet[0]
        seqnum      = packet[1]
        asn_gen     = packet[2]
        buffer_pos  = packet[3]
        cex_packet = ({'cex_src': moteid, 'seqnum':seqnum, 'asn':asn_gen})
    

        # will now explore all the transmissions for this cexample packet
        cex_packet['l2_transmissions'] = cex_l2transmissions_for_cex_packet(con, cex_packet, dagroot_ids, moteid, buffer_pos, asn_gen, l2tx_pd)
        
        
        if cex_packet['l2_transmissions'] is not None:
            cex_packets_stats.append(cex_packet)
   
    return(cex_packets_stats)
          
    

    
#main (multithreading safe)
if __name__ == "__main__":

    #parameters
    args = init()

  
    for experiment in os.listdir(args.dir):
        db_filename = os.path.join(args.dir, experiment, DB_FILENAME)
        json_filename = os.path.join(args.dir, experiment, JSON_FILENAME)
          
                  
        #a db exists, and has not been processed
        to_process = (os.path.isfile(json_filename) is False) or (args.rewrite)
        
        print("------------------------------------------------------------------------------------------------")
        print("SUBDIR |{}| => db={}, json_exists={}, rewrite={}  ".format(
                os.path.join(args.dir, experiment),
                os.path.isfile(db_filename),
                os.path.isfile(json_filename),
                args.rewrite
        ))
        
        merge_sqllite_db(os.path.join(args.dir, experiment))
        
        
        if (to_process) and (os.path.isfile(db_filename) is True):
            print("db {}".format(db_filename))
            
            #parameters, etc.
            con = db_create_connection(db_filename)

            # ---- MOTES & CONFIG ----
            motes = motes_get(con)
            print("Nb. Motes={} ".format(len(motes)))
            dagroot_ids = dagroot_ids_get(con)
            asn_end = asn_end_get(con)
            print("Duration={}min".format(asn_end * 25 / 60000))
            
            #--- RAW layer 2 transmisisons ------
            #anycast/unicast links
            links = links_get(con)
            l2tx = l2tx_get(con)
            print("Nb. l2tx={} ".format(len(l2tx)))

             
            #  ----- CEXAMPLE ----- track tx for each app packet
            l2tx_pd = pd.DataFrame.from_dict(l2tx)
            cex_packets = cex_packets_end2end(con, dagroot_ids, l2tx_pd)

            print("Nb. Cexample packets={}".format(len(cex_packets)))

            if False:
                for cex_packet in cex_packets:
                    print(cex_packet)
                
                    #print("src={0}, seqnum={1}".format(cex_packet['cex_src'], cex_packet['seqnum']))
                    #for elem in cex_packet['l2_transmissions']:
                    #    print("        {0}".format(cex_packet['l2_transmissions']))
                    #print("------")
        
            #store everything in json file
            data = {}
            data['motes']           = motes
            data['links']           = links
            data['cex_packets']     = cex_packets
            data['l2tx']            = l2tx
            data['dagroot_ids']     = dagroot_ids
            data['asn_end']         = asn_end
            data['configuration']   = configuration_get(con)
            data['configuration']['nbmotes'] = len(motes)
            data['configuration']['experiment'] = experiment
            
            
            with open(json_filename, 'w') as outfile:
                json.dump(data, outfile)
                
                
            #end for this experiment
            con.close()
            
            
    sys.exit(0)



