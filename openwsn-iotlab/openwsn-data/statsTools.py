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

#FIFO
from collections import deque

#plot
import pandas as pd
from IPython.display import display



#for real stats
PARAM_MIN_TX = 70               #discard all the stats where less than X packets have been generated
PARAM_MIN_ACKTX = 2             # disard flows with not enough ack txed (typically unused secondary receivers
PARAM_ASN_MARGIN_START = 1000   # discard the last X timeslots (25ms)
PARAM_ASN_MARGIN_END = 500      # discard the first X timeslots (25ms)


#for debuging
if True:
    PARAM_MIN_TX = 0               #discard all the stats where less than X packets have been generated
    PARAM_MIN_ACKTX = 0             # disard flows with not enough ack txed (typically unused secondary receivers
    PARAM_ASN_MARGIN_START = 0   # discard the last X timeslots (25ms)
    PARAM_ASN_MARGIN_END = 0      # discard the first X timeslots (25ms)



class rxFound(Exception):
    """
    The final destinatio has been found
    """
    pass
    
    
#extracts and classifies cexample info
def cexample_compute_indiv(experiment, datafile, flowStats):
    
    #init if the variable doesn't exist
    if flowStats is None:
        #stats for cexample flows (dictionary to be used later by pandas)
        flowStats = {}
        flowStats['cex_src'] = []
        flowStats['seqnum'] = []
        flowStats['time_min'] = []
        flowStats['delivered'] = []
        flowStats['delay_ts'] = []
        flowStats['delay_ms'] = []
        flowStats['nb_l2tx'] = []
        flowStats['nbmotes'] = []
        flowStats['cexample_period'] = []
        flowStats['sixtop_anycast'] = []

        
    #track tx for each app packet
    print("")
    print("------ Statistics -- {0} -----".format(experiment))

    #PDR per source
    stats = {}
    
    #display(datafile['cex_packets'][0])
    #print("dagroots: {}".format(datafile['dagroot_ids']))
    
    for cex_packet in datafile['cex_packets']:
        
        #don't handle the packets that have been generated too late or too early
        if cex_packet['asn'] < PARAM_ASN_MARGIN_START or cex_packet['asn'] > datafile['asn_end'] - PARAM_ASN_MARGIN_END :
            break
        
        #search for the hop that received the packet
        #print("----{} ---".format(len(cex_packet['l2_transmissions'])))

        delay_ts = 0
        is_rcvd = False
        for l2tx in cex_packet['l2_transmissions']:
            #print(l2tx)
            for rx in l2tx['receivers']:
                #print("  --> {}".format(rx['moteid']))
                if rx['moteid'] in datafile['dagroot_ids']:
                    is_rcvd = True
                    delay_ts = l2tx['asn'] - cex_packet['asn']
        #print("-----")
        #print("{} {}".format(is_rcvd, delay_ts))

        
        flowStats['cex_src'].append(cex_packet['cex_src'])
        flowStats['seqnum'].append(cex_packet['seqnum'])
        flowStats['time_min'].append(cex_packet['asn'] * 25 /(1000*60))
        flowStats['delivered'].append(is_rcvd)
        flowStats['delay_ts'].append(delay_ts)
        flowStats['delay_ms'].append(delay_ts * 25)
        flowStats['nb_l2tx'].append(len(cex_packet['l2_transmissions']))
        flowStats['nbmotes'].append(datafile['configuration']['nbmotes'])
        flowStats['cexample_period'].append(datafile['configuration']['cexample_period'])
        flowStats['sixtop_anycast'].append(datafile['configuration']['sixtop_anycast'])

        
        
    #display(flowStats)
    return flowStats
            
                    
            






#extracts and classifies cexample info
def cexample_compute_agg(experiment, datafile, flowStats):
    
    #init if the variable doesn't exist
    if flowStats is None:
        #stats for cexample flows (dictionary to be used later by pandas)
        flowStats = {}
        flowStats['cex_src'] = []
        flowStats['nbmotes'] = []
        flowStats['cexample_period'] = []
        flowStats['sixtop_anycast'] = []
        flowStats['nb_gen'] = []
        flowStats['pdr'] = []
        flowStats['delay_ts'] = []
        flowStats['delay_ms'] = []
        flowStats['nb_l2tx_raw'] = []
        flowStats['nb_l2tx_norm'] = []

        
    #track tx for each app packet
    print("")
    print("------ Statistics -- {0} -----".format(experiment))

    #PDR per source
    stats = {}
     
    for cex_packet in datafile['cex_packets']:
        if cex_packet['cex_src'] == '44054332ff03dab369':
            DEBUG = True
        else:
            DEBUG = False
    
    
        #don't handle the packets that have been generated too late or too early
        if cex_packet['asn'] < PARAM_ASN_MARGIN_START or cex_packet['asn'] > datafile['asn_end'] - PARAM_ASN_MARGIN_END :
        
            print("discard packets for flow {}".format(cex_packet['cex_src']))
            break

        if DEBUG:
            print(cex_packet)


        #creates the key for this src device if it doesn't exist yet
        if cex_packet['cex_src'] in stats:
            stats[cex_packet['cex_src']]['nb_gen'] = stats[cex_packet['cex_src']]['nb_gen'] + 1
        else:
            stats[cex_packet['cex_src']] = {}
            stats[cex_packet['cex_src']]['nb_gen'] = 1
            stats[cex_packet['cex_src']]['nb_rcvd'] = 0
            stats[cex_packet['cex_src']]['delay'] = 0
            stats[cex_packet['cex_src']]['nb_l2tx'] = 0
        
        try:
            if DEBUG:
                print("seqnum={}/asn={}".format(cex_packet['seqnum'], cex_packet['asn']))
                
                for elem in cex_packet['l2_transmissions']:
                    print("    src={}, asnTx={}, receivers:".format(elem['l2src'], elem['asn']))
                    for elem2 in elem['receivers']:
                        print("       {}".format(elem2))
        
            stats[cex_packet['cex_src']]['nb_l2tx'] += len(cex_packet['l2_transmissions'])
            for l2tx in cex_packet['l2_transmissions']:
                for rcvr in l2tx['receivers']:
                    if rcvr['moteid'] in datafile['dagroot_ids'] :
                        if (DEBUG):
                            print("{} ===== {}".format(rcvr['moteid'], datafile['dagroot_ids']))
                        stats[cex_packet['cex_src']]['nb_rcvd'] += 1 #stats[cex_packet['cex_src']]['nb_rcvd'] +1
                        stats[cex_packet['cex_src']]['delay'] += l2tx['asn'] - cex_packet['asn']
                        raise(rxFound)
                    elif DEBUG:
                        print("{} != {}".format(rcvr['moteid'], datafile['dagroot_ids']))
        #we found one of the dagroot ids -> pass to the next cex packet
        except rxFound as evt:
            pass
        
        if DEBUG:
            print("")
            print("")
            print("")

    print("Per cexample flow")
    for value in stats:
        #if the stat is significant (synchronized node)
        if (stats[value]['nb_gen'] > PARAM_MIN_TX):

                
            #everything in a big array (one line per flow)
            flowStats['cex_src'].append(value)
            flowStats['nbmotes'].append(datafile['configuration']['nbmotes'])
            flowStats['cexample_period'].append(datafile['configuration']['cexample_period'])
            flowStats['sixtop_anycast'].append(datafile['configuration']['sixtop_anycast'])
            flowStats['nb_gen'].append(stats[value]['nb_gen'])
            flowStats['pdr'].append(stats[value]['nb_rcvd'] / stats[value]['nb_gen'])
            flowStats['nb_l2tx_raw'].append(stats[value]['nb_l2tx'] / stats[value]['nb_gen'])
            if (stats[value]['nb_rcvd'] > 0):
                flowStats['delay_ts'].append(stats[value]['delay'] / stats[value]['nb_rcvd'])
                flowStats['delay_ms'].append(25 * stats[value]['delay'] / stats[value]['nb_rcvd'])
                flowStats['nb_l2tx_norm'].append(stats[value]['nb_l2tx'] / stats[value]['nb_rcvd'])
            else:
                flowStats['delay_ts'].append(0)
                flowStats['delay_ms'].append(0)
                flowStats['nb_l2tx_norm'].append(0)
    return flowStats
            
                    
            



#raw layer 2 transmissions
def l2tx_compute(datafile, l2txStats):
   
    #init if the variable doesn't exist
    if l2txStats is None:
    #stats for l2 frame transmsisions
        l2txStats = {}
        l2txStats['nbmotes'] = []
        l2txStats['cexample_period'] = []
        l2txStats['sixtop_anycast'] = []
        l2txStats['moteid_tx'] = []
        l2txStats['moteid_rx'] = []
        l2txStats['slotOffset'] = []
        l2txStats['priority_rx'] = []
        l2txStats['numDataTx'] = []
        l2txStats['numDataRx'] = []
        l2txStats['PDRData'] = []
        l2txStats['numAckTx'] = []
        l2txStats['numAckRx'] = []
        l2txStats['PDRAck'] = []
        l2txStats['NbHiddenRx'] = []
        l2txStats['RatioHiddenRx'] = []
        l2txStats['intrpt_RatioCCA'] = []
        l2txStats['intrpt_CCA'] = []
        l2txStats['intrpt_SFD'] = []

  
    # ------- Raw l2 tx -------
    print("-- l2 tx")

    #Panda values (separating anycast and unicast)
    l2tx_pdr_raw_pd = pd.DataFrame.from_dict(datafile['l2tx'])

    if l2tx_pdr_raw_pd.empty :
        print("Empty data frame")
        return(l2txStats)


    #discard shared and auto cells
    l2tx_pdr_raw_pd = l2tx_pdr_raw_pd[
        (l2tx_pdr_raw_pd['shared'] == 0) &
        (l2tx_pdr_raw_pd['autoCell'] == 0) &
        (l2tx_pdr_raw_pd['asn'] > PARAM_ASN_MARGIN_START) &
        (l2tx_pdr_raw_pd['asn'] < datafile['asn_end'] - PARAM_ASN_MARGIN_END)
    ]
    
    #group by TX (to count the  of txed packets)
    l2tx_groupbycelltx_pd = l2tx_pdr_raw_pd.groupby(["moteid_tx","slotOffset", "channelOffset"]).agg({"asn":"count"}).reset_index().sort_values(by=['slotOffset'])
    
    #group by RX (to count the number of rcvd packets)
    l2tx_groupbycellrx_pd = l2tx_pdr_raw_pd.groupby(["moteid_tx","slotOffset", "channelOffset", "moteid_rx"], dropna=True).agg({"asn":"count","priority_rx":"mean", "crc_data":"sum", "ack_tx":"sum", "crc_ack":"sum"}).reset_index().sort_values(by=['slotOffset'])
     
    #print("------")
    #display(l2tx_pdr_raw_pd[(l2tx_pdr_raw_pd['priority_rx'] > 0)])
    #print("------")
    #display(l2tx_groupbycelltx_pd)
    #print("------")
    #display(l2tx_groupbycellrx_pd)
    #print("------")
 
      
    #identify all the occurences of double ACK tx
    #NB: the joint is symetrical (moteid_rx_x,moteid_rx_y) exists ->  (moteid_rx_y,moteid_rx_x) exists
    hidden_rx_pd = l2tx_pdr_raw_pd[(l2tx_pdr_raw_pd['ack_tx']==True)]
    hidden_rx_pd = hidden_rx_pd.merge(hidden_rx_pd, on= ['asn','slotOffset', 'channelOffset'])[['asn', 'slotOffset', 'moteid_tx_x', 'moteid_rx_x', 'moteid_rx_y', 'ack_tx_x', 'ack_tx_y']]
    hidden_rx_pd = hidden_rx_pd[(hidden_rx_pd['moteid_rx_x'] != hidden_rx_pd['moteid_rx_y'])]
    #display(hidden_rx_pd)

    #PARAM_MIN_TX = 0
      
    #notna = pd.notna(l2tx_groupbycellrx_pd["moteid_rx"])
    for index in l2tx_groupbycellrx_pd.index:
        
        #print("moteid rx {}, tx {}".format(
        #            l2tx_groupbycellrx_pd['moteid_rx'][index],
        #            l2tx_groupbycellrx_pd['moteid_tx'][index]
        #        ))
    
        #retrieves the number of txed packets in this cell
        numTx_pd = l2tx_groupbycelltx_pd[(l2tx_groupbycelltx_pd['moteid_tx'] == l2tx_groupbycellrx_pd['moteid_tx'][index]) ].reset_index()
        numTx_pd = numTx_pd[
            (numTx_pd['slotOffset'] == l2tx_groupbycellrx_pd['slotOffset'][index]) &
            (numTx_pd['channelOffset'] == l2tx_groupbycellrx_pd['channelOffset'][index])        
        ].reset_index()
        numTx = numTx_pd['asn'].iloc[0]
          
        #everything in a big array (one line per flow)
        if (numTx > PARAM_MIN_TX) and (l2tx_groupbycellrx_pd['ack_tx'][index] > PARAM_MIN_ACKTX) :
            
            #test only on moteid_rx_x since the JOINT is symetrical
            hidden_list = hidden_rx_pd[
                        (hidden_rx_pd['moteid_rx_x'] == l2tx_groupbycellrx_pd['moteid_rx'][index]) &
                        (hidden_rx_pd['slotOffset'] == l2tx_groupbycellrx_pd['slotOffset'][index])
            ]
            #print("{} -> {}".format(l2tx_groupbycellrx_pd['moteid_tx'][index], l2tx_groupbycellrx_pd['moteid_rx'][index]))
            #display(hidden_list)
            
            #nb of acks txed by the primary receiver (for normalization)
            acktx_pd = l2tx_pdr_raw_pd[
            (l2tx_pdr_raw_pd['slotOffset'] == l2tx_groupbycellrx_pd['slotOffset'][index]) &
            (l2tx_pdr_raw_pd['moteid_tx'] == l2tx_groupbycellrx_pd['moteid_tx'][index]) &
            (l2tx_pdr_raw_pd['priority_rx'] == 0)
            ]
            
            #for secondary receivers: ratio CCA / SFD
            if l2tx_groupbycellrx_pd['priority_rx'][index] > 0:
                
                
                rx_list = l2tx_pdr_raw_pd[
                        (l2tx_pdr_raw_pd['moteid_rx'] == l2tx_groupbycellrx_pd['moteid_rx'][index]) &
                        (l2tx_pdr_raw_pd['slotOffset'] == l2tx_groupbycellrx_pd['slotOffset'][index]) &
                        #(l2tx_pdr_raw_pd['asn'] == l2tx_groupbycellrx_pd['asn'][index])
                        (l2tx_pdr_raw_pd['moteid_tx'] == l2tx_groupbycellrx_pd['moteid_tx'][index])
                ]
                #display(rx_list)
                
                CCA_list = rx_list[(rx_list['intrpt'] == "CCA_BUSY")]
                CCA_nb = len(CCA_list)
                SFD_list = rx_list[(rx_list['intrpt'] == "STARTOFFRAME")]
                SFD_nb = len(SFD_list)
                if (CCA_nb + SFD_nb > 0):
                    CCA_ratio = CCA_nb/ (CCA_nb + SFD_nb)
                else:
                    CCA_ratio = 0
            else:
                CCA_nb = 0
                SFD_nb = 0
                CCA_ratio = 0

            
            l2txStats['nbmotes'].append(datafile['configuration']['nbmotes'])
            l2txStats['cexample_period'].append(datafile['configuration']['cexample_period'])
            l2txStats['sixtop_anycast'].append(datafile['configuration']['sixtop_anycast'])
            l2txStats['moteid_tx'].append(l2tx_groupbycellrx_pd['moteid_tx'][index])
            l2txStats['moteid_rx'].append(l2tx_groupbycellrx_pd['moteid_rx'][index])
            l2txStats['slotOffset'].append(l2tx_groupbycellrx_pd['slotOffset'][index])
            l2txStats['priority_rx'].append(l2tx_groupbycellrx_pd['priority_rx'][index])
            l2txStats['numDataTx'].append(numTx)
            l2txStats['numDataRx'].append(l2tx_groupbycellrx_pd['crc_data'][index])
            l2txStats['PDRData'].append(l2tx_groupbycellrx_pd['crc_data'][index] / numTx)
            l2txStats['numAckTx'].append(l2tx_groupbycellrx_pd['ack_tx'][index])
            l2txStats['numAckRx'].append(l2tx_groupbycellrx_pd['crc_ack'][index])
            l2txStats['PDRAck'].append(l2tx_groupbycellrx_pd['crc_ack'][index] / l2tx_groupbycellrx_pd['ack_tx'][index])
            l2txStats['NbHiddenRx'].append(len(hidden_list))
            if (len(acktx_pd) > 0):
                l2txStats['RatioHiddenRx'].append(len(hidden_list) / len(acktx_pd))
            else:
                 l2txStats['RatioHiddenRx'].append(0)
            l2txStats['intrpt_RatioCCA'].append(CCA_ratio)
            l2txStats['intrpt_CCA'].append(CCA_nb)
            l2txStats['intrpt_SFD'].append(SFD_nb)


            if False and len(hidden_list) / len(acktx_pd) > 0.2:
                print("")
                print("ratio high: {}: {} idtx {} idrx {} list {}".format(
                datafile['configuration']['experiment'],
                len(hidden_list) / len(acktx_pd),
                l2tx_groupbycellrx_pd['moteid_tx'][index],
                l2tx_groupbycellrx_pd['moteid_rx'][index],
                len(hidden_list)

                ))
                print("--------")
                print("")

                display(l2tx_groupbycellrx_pd[(l2tx_groupbycellrx_pd['moteid_tx'] == l2tx_groupbycellrx_pd['moteid_tx'][index])])

            #print(">>> id{}, offset={}: nbfalsepositive={}".format(
            #            l2tx_groupbycellrx_pd['moteid_rx'][index],
            #            l2tx_groupbycellrx_pd['slotOffset'][index],
            #            len(hidden_list)
            #))
    
    #print("--------")
    return l2txStats
    




