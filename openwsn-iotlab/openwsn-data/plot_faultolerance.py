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






 
#fault tolerance graphs
def timePerfs_plot(flowStats):
    
    #Panda values (separating anycast and unicast)
    print("-- flowStats statistics")
    flowStats_pd = pd.DataFrame.from_dict(flowStats)
    print(flowStats_pd)


    #delay
    plot = sns.scatterplot(x='time_min', y='delay_ms', data=flowStats_pd[(flowStats_pd['sixtop_anycast'] == 1)])
    plot.set_xlabel("#of timeslots since the beginning")
    plot.set_ylabel("Delay in ms")
    plot.set(ylim=(0,5000))
    plot.set(xlim=(0,30))
    plot.figure.savefig("plots/fault_delay_anycast.pdf")
    plot.figure.clf()

    plot = sns.scatterplot(x='time_min', y='delay_ms', data=flowStats_pd[(flowStats_pd['sixtop_anycast'] == 0)])
    plot.set_xlabel("#of timeslots since the beginning")
    plot.set_ylabel("Delay in ms")
    plot.set(ylim=(0,5000))
    plot.set(xlim=(0,30))
    plot.figure.savefig("plots/fault_delay_noanycast.pdf")
    plot.figure.clf()




#ASN_nonanycast=49829

if __name__ == "__main__":

    
    #no type 3 font
    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42

      
    #prepare the stats for pandas
    flowStats = None


    for experiment in ['results/fault-tolerance/owsn-0YUS688H-withanycast', 'results/fault-tolerance/owsn-7C4YZ65L-noanycast']:
        
        json_filename = os.path.join(experiment, "stats.json")
        print(json_filename)
        
        if os.path.isfile(json_filename) is True:
            print(json_filename)
            with open(json_filename) as json_file:
                datafile = json.load(json_file)
           
            #organizes the stats for cexample
            flowStats = statsTools.cexample_compute_indiv(experiment, datafile, flowStats)
           
       
    #plot the figures for cexample
    timePerfs_plot(flowStats)
     
    #end
    print("End of the computation")

            
            
    sys.exit(0)




