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
import seaborn as sns
from IPython.display import display
import matplotlib


#aux lib
import statsTools



#initialization: args + sqlite connection
def init():
    #parsing arguments
    parser = argparse.ArgumentParser(description='plot graphs with the data processed in a json file.')

    parser.add_argument('--dir',
                        default="./results",
                        help='directory to parse (one directory per experiment)')
    args = parser.parse_args()
    print("DIR:{0}".format(args.dir))
    return(args)

 
                    
                    
#plot the figures for cexample stats
def cexample_plot(flowStats_pd):
    
    #Panda values (separating anycast and unicast)
    print("-- Cexample flows")
    #flowStats_pd = flowStats_pd[flowStats_pd['nbmotes'] < 200].reset_index()
    
    
    #common sns config
    sns.set_theme(style="ticks")
    #PDR
    plot = sns.violinplot(x='nbmotes', y='pdr', hue='sixtop_anycast',cut=0, legend_out=True, data=flowStats_pd)
    plot.legend(handles=plot.legend_.legendHandles, labels=['without anycast', 'with anycast'])
    plot.set_xlabel("Number of motes")
    plot.set_ylabel("Packet Delivery Ratio")
    #plot.set(yscale="log")
    #plot.set(ylim=(1e-2,1))
    plot.set(ylim=(0,1))
    plot.figure.savefig("plots/cexample_pdr.pdf")
    plot.set_xticks(np.arange(50, 100, 10))
    plot.figure.clf()
    
    #PDR
    plot = sns.violinplot(x='nbmotes', y='delay_ms', hue='sixtop_anycast',cut=0,data=flowStats_pd)
    plot.legend(handles=plot.legend_.legendHandles, labels=['without anycast', 'with anycast'])
    plot.set_xlabel("Number of motes")
    plot.set_ylabel("Delay (in ms)")
    plot.figure.savefig("plots/cexample_delay.pdf")
    plot.figure.clf()
        
    #Efficiency
    plot = sns.violinplot(x='nbmotes', y='nb_l2tx_raw', hue='sixtop_anycast',cut=0,data=flowStats_pd)
    plot.legend(handles=plot.legend_.legendHandles, labels=['without anycast', 'with anycast'])
    plot.set_xlabel("Number of motes")
    plot.set_ylabel("Number of transmissions per message")
    plot.figure.savefig("plots/cexample_nb_l2tx.pdf")
    plot.figure.clf()
   
    print("")
    print("")
    
 
                    
#plot the figures for cexample stats
def l2tx_plot(l2txStats_pd):
    
    #Panda values (separating anycast and unicast)
    print("-- l2txStats statistics")
    print(l2txStats_pd)
    
    #common sns config
    sns.set_theme(style="ticks")

    #PDR for acks vs. data packets
    plot = sns.scatterplot(x='PDRData', y='PDRAck', data=l2txStats_pd)
    plot.set_xlabel("Packet Delivery Ratio (data)")
    plot.set_ylabel("Packet Delivery Ratio (ack)")
    plot.figure.savefig("plots/l2tx_pdr_bidirect.pdf")
    plot.figure.clf()
    
    #hidden receiver problem
    secondaryrx_pd = l2txStats_pd[(l2txStats_pd['priority_rx'] == 1)];
    plot = sns.scatterplot(x='PDRData', y='RatioHiddenRx', data=secondaryrx_pd)
    plot.set_xlabel("Packet Delivery Ratio (data)")
    plot.set_ylabel("Ratio of False Negatives")
    plot.set(yscale="log")
    plot.set(ylim=(1e-3,1))
    plot.figure.savefig("plots/l2tx_hidden_receiver_falseneg.pdf")
    plot.figure.clf()

    #CCA / SFD identification vs. link PDR
    plot = sns.scatterplot(x='PDRData', y='intrpt_RatioCCA', data=secondaryrx_pd)
    display(secondaryrx_pd)
    plot.set_xlabel("Packet Delivery Ratio (data)")
    plot.set_ylabel("Ratio CCA / Start of Frame interruptions")
    plot.set(ylim=(0,1))
    plot.figure.savefig("plots/l2tx_ratioCCA-SFD_PDR.pdf")
    plot.figure.clf()
    
    
    #CCAratio vs. hidden receivers
    plot = sns.scatterplot(x='RatioHiddenRx', y='intrpt_RatioCCA', data=secondaryrx_pd)
    display(secondaryrx_pd)
    plot.set_xlabel("Ratio of false negatives ACK detection (hidden receivers)")
    plot.set_ylabel("Ratio CCA / Start of Frame interruptions")
    plot.set(ylim=(0,1))
    plot.figure.savefig("plots/l2tx_ratioCCA-SFD_hiddenrx.pdf")
    plot.figure.clf()


    print("")
    print("")
    

if __name__ == "__main__":

    
    #no type 3 font
    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42

    #parameters
    args = init()
    
    #init
    flowStats = None
    l2txStats = None
    
    #prepare the stats for pandas
    for experiment in os.listdir(args.dir):
        json_filename = os.path.join(args.dir, experiment, "stats.json")
        
        if os.path.isfile(json_filename) is True:
            print(json_filename)
            with open(json_filename) as json_file:
                datafile = json.load(json_file)
           
            #organizes the stats for cexample
            flowStats = statsTools.cexample_compute_agg(experiment, datafile, flowStats)

            #compute the stats for l2tx
            l2txStats = statsTools.l2tx_compute(datafile, l2txStats)
    
    
    
    cex_packets_pd = pd.DataFrame.from_dict(datafile['cex_packets'])
    for index, row in cex_packets_pd[(cex_packets_pd['cex_src'] == '054332ff03d88982')].iterrows():
        print("seqnum {}".format(row['seqnum']))
        display(row['l2_transmissions'])
    
    #plot the figures for cexample
    flowStats_pd = pd.DataFrame.from_dict(flowStats)
    display(flowStats_pd)
    #cexample_plot(flowStats_pd)

    #plot the figures for link stats
    l2txStats_pd = pd.DataFrame.from_dict(l2txStats)
    display(l2txStats_pd)
    #l2tx_plot(l2txStats_pd)
    
   
 
    #end
    print("End of the computation")

        
            
            
    sys.exit(0)



