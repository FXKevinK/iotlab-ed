#!/usr/bin/env python3
# coding: utf-8



# systems tools
import os
import shutil
import sys
import time
import sys
import signal
import random
import datetime

# multiprocess
import threading
import psutil

#format
import string
import json

#custom libraries
import iotlabowsn

NEWEXP = False
COMPIL = True
SIMULATION = False
    
    
    
#configuration for the experimenal setup (what stays unchanged)
def configuration_set():
    config = {}

    #paths
    config['path_initial'] = os.getcwd()
    print("Inital path: {0}".format(config['path_initial']))
    
    config['path_results_root'] = "/home/theoleyre/openwsn/results/"
    config['path_results_root_crash'] = config['path_results_root'] + "/crash"
    config['path_results_root_finished'] = config['path_results_root'] + "/valid"
    os.makedirs(config['path_results_root_crash'], exist_ok=True)
    os.makedirs(config['path_results_root_finished'], exist_ok=True)

    # Metadata for experiments
    config['user']="theoleyr"
    config['subexp_duration']=60      # for one run (one set of parameters), in minutes
    config['exp_duration']=config['subexp_duration'] * 2 + 30        # for the iot lab reservation (collection of runs), in minutes (two experiments + a safety margin)
    config['exp_resume']=True           # restart an already running experiment (if one exists)
    config['exp_resume_verif'] = False  # verification that the motes are those specified (in the running exp)
    config['exp_name']="LS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Parameters of the experiment
    config['board']="iot-lab_M3"
    config['toolchain']="armgcc"
    config['archi']="m3"
    config['site']="grenoble"
    config['maxid']=289             #discard larger node's ids
    config['minid']=70              #discard smaller node's ids
    config['maxspaceid']=9          #max separation with the closest id
    
    
    #for simulation
    if SIMULATION:
        config['board']="python"
        config['toolchain']="gcc"
        config['topology']="--load-topology " + config['path_initial'] + "/topologies/topology-3nodes.json"
    
    
    # openvisualizer directory
    config['code_sw_src'] = config['path_initial'] + "/../openvisualizer/"
    if (os.path.exists(config['code_sw_src']) == False):
        print("{0} does not exist".format(config['code_sw_src']))
        exit(-4)
    config['code_sw_gitversion']="525b684"

    # coap directory
    config['code_coap_src'] = config['path_initial'] + "/../coap/"
    if (os.path.exists(config['code_coap_src']) == False):
        print("{0} does not exist".format(config['code_coap_src']))
        exit(-4)
    config['code_coap_gitversion']="5df88ab"


    # firmware part
    config['code_fw_src']= config['path_initial'] + "/../openwsn-fw/"
    if (os.path.exists(config['code_fw_src']) == False):
        print("{0} does not exist".format(config['code_fw_src']))
        exit(-4)
    config['code_fw_gitversion']="515eafa7"
    config['code_fw_bin']=config['code_fw_src']+"build/iot-lab_M3_armgcc/projects/common/03oos_openwsn_prog"
    
 
    return(config)



        
        

#prints the headers of a section
def print_header(msg):
    print("\n\n---------------------------------------------")
    print("     " + msg)
    print("---------------------------------------------\n\n")


#clean up
def cleanup_subexp(error=False):
    print_header("Cleanup")

    if (error == False):
        print("Everything was ok -> move the files {0} in {1}". format(config['path_results'], config['path_results_root_finished']))

        file = open(config['path_results'] + "/_ok.txt", 'w')
        file.write("ok\n")
        file.close()
        
        shutil.move(config['path_results'], config['path_results_root_finished'])
    else:
        print("Something went wrong -> move the files {0} in {1}". format(config['path_results'], config['path_results_root_crash']))
        shutil.move(config['path_results'], config['path_results_root_crash'])
        
    del config['path_results']
    
        
#signal protection
def kill_all(sig, frame):
  
    #cleanup the directory result
    if 'path_results' in config:
        cleanup_subexp(sig == signal.SIGUSR1)
    #stop the experiment (iotlab)
    if config['exp_id'] != 0:
        iotlabowsn.exp_stop(config['exp_id'])

    #kill everything
    process = psutil.Process(os.getpid())
    for proc in process.children(recursive=True):
        print("killing {0}".format(proc))
        proc.kill()
        print("..killed")
    if (sig == signal.SIGUSR1):
        sys.exit(0)
    else:
        sys.exit(3)
 


def nodes_selection(config, nbnodes):
    #construct the list of motes
    print_header("Nodes Selection")
    testbed_nodealive_list = iotlabowsn.get_nodes_list(config["site"], config["archi"], "Alive")
    nbtest=0
    config['nodes_list'] = []

    #insert iteratively the motes
    while(len(config['nodes_list']) < nbnodes):
        connected = False
        while(connected is False):
        
            #pick a random id in the list (not already present in the selection
            while (True):
                new = random.randint(0, len(testbed_nodealive_list)-1)
                new = int(testbed_nodealive_list[new])
                
                #this id is a priori ok
                if ((new >= config['minid']) and (new <= config['maxid']) and (new not in config['nodes_list'])):
                    #print(new)
                    break
                    
            #print("test {0} in {1} {2}".format(new, config['nodes_list'], len(config['nodes_list'])))
            
            #the list is not null
            if (len(config["nodes_list"]) > 0):
                
                #an id in the list is close to this novel one
                for node in config['nodes_list']:
                    if (abs(node - new) <= config['maxspaceid']):
                        connected = True
                        break
                    
            # the first id is ok, whatever it is
            else:
                connected = True
            
            if (connected):
                config["nodes_list"].append(new)
                
            
            #too many fails -> restart from scratch
            #print("nbtest {0}".format(nbtest))
            nbtest = nbtest + 1
            if (nbtest > 15 * nbnodes):
                print("too many fails -> flush the list to start from scratch")
                config['nodes_list'].clear()
                nbtest=0


    #cleanup + dagroot selection (first mote in the list)
    config['nodes_list'].sort(key=int)
    config['dagroots_list'] = [config['nodes_list'][0], ]
    config['nodes_list'].remove(config['dagroots_list'][0])
    print("Nodes list: {0}".format(config["nodes_list"]))
    print("Dagroot: {0}".format(config["dagroots_list"]))


    return config


# ---- RESERVATION /RESUME EXPERIMENT ----

def experiment_reservation(config):
    print_header("Reservation (experiment)")
    if ( config['exp_resume'] == True):
        config['exp_id'] = iotlabowsn.get_running_id(config);
    else:
        config['exp_id'] = None
        
    if config['exp_id'] is not None:
        print("Resume the experiment id {0}".format(config['exp_id']))
        print("with the motes {0}".format(config['nodes_list']))
        print("and dagroots {0}".format(config['dagroots_list']))
    else:
        config['exp_id'] = iotlabowsn.exp_start(config)
    
    print("Wait the experiment is in running mode")
    iotlabowsn.exp_wait_running(config['exp_id'])
    
    return config['exp_id']


def experiment_execute(config):
    
    #final results
    dirs_res = os.listdir(config['path_results_root'])
    dirs_trash =  os.listdir(config['path_results_root_crash'])
    dirs_finished =  os.listdir(config['path_results_root_finished'])
    config['path_results'] = "owsn-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    config['path_results'] = config['path_results_root'] + config['path_results']
    os.makedirs(config['path_results'])
    print("Results Path {0}".format(config['path_results']))


    # ---- CONFIG----
 
    #openvisualizer configuration
    config['conf_file'] = config['path_results'] + "/logging.conf"
    config['conf_file_start'] = config['path_initial'] + "/loggers/logging_start.conf"
    config['conf_file_end'] = config['path_initial'] + "/loggers/logging_end.conf"

    #saves the config
    file = open(config['path_results']+"/params.txt", 'w')
    json.dump(config, file)
    file.close()
    
    
    # ---- COMPIL + FLASHING----

    if COMPIL:
        print_header("Compilation")
        iotlabowsn.compilation_firmware(config)

        if config['board']=="iot-lab_M3":
            print_header("Flashing")
            iotlabowsn.flashing_motes(config['exp_id'], config)


    # ---- OpenVisualizer ----

    print_header("Openvizualiser")
    iotlabowsn.openvisualizer_create_conf_file(config)
  
    #wait that openvizualizer is properly initiated
    nb_try = 0
    while True:
        time_start = time.time()
        t_openvisualizer = iotlabowsn.openvisualizer_start(config)
        nbmotes = None
        while nbmotes is None:
            nbmotes = iotlabowsn.openvisualizer_nbmotes()
        
            print("nb motes : {0}".format(nbmotes))
        
            #crash -> restart openvisualizer
            if t_openvisualizer.is_alive() is False:
                print("Openvisualizer seems have crashed / stopped")
                break
                
            #wait 2 seconds before trying to connect to the server
            if nbmotes is None:
                print("openvisualizer is not yet running")
                time.sleep(1)
                
        #the nb of running motes matches the config
        if nbmotes == config['nb_nodes']:
            print("All the motes are connected to openvisualizer")
            break
        else:
            print("Only {0} motes are connected, we restart openvisualizer {1} try".format(nbmotes, nb_try))
            
        #else, we have a bug
        nb_try = nb_try + 1
        
        #stops openvisualizer
        if t_openvisualizer.is_alive() is True:
            print("Cleanning up children process".format(t_openvisualizer))
            process = psutil.Process(os.getpid())
            for proc in process.children(recursive=True):
                print("killing {0}".format(proc))
                proc.kill()
                print("..killed")
        
        if nb_try > 10:
            print("Openvisualizer seems failing even after having been restarted {0} times, stops here". format(nb_try))
            sys.exit(-3)
            
        time.sleep(3)

    # ---- Openweb server (optional, for debuging via a web interface) ----

    print_header("Openweb server")
    t_openwebserver = iotlabowsn.openwebserver_start(config)
    

    # ---- Boots the motes (not in simulation mode) ----
    print_header("Configure Motes")
    if config['board'] == 'iot-lab_M3':
        iotlabowsn.mote_boot(config['exp_id'])
        valid_dagroot_config = iotlabowsn.dagroot_set(config)
    else:
        valid_dagroot_config = True
    
    
    #--- running experiment verification ----
    if (valid_dagroot_config is True):

        # ---- Exp running ----

        print_header("Execution")
        print("gpid me: {0}".format(os.getpgid(os.getpid())))
        print("pid me: {0}".format(os.getpid()))

        print("nb threads = {0}".format(threading.active_count()))

        #every second, let us verify that the openvizualizer thread is still alive
        counter = 0
        while (t_openvisualizer is not None and t_openvisualizer.is_alive()):
            counter = counter + 1
            if (counter >= 60):
                print("thread {0} is alive, {1}s < {2}min".format(t_openvisualizer, time.time() - time_start, config['subexp_duration']))
                counter = 0
            time.sleep(1)

    #everything was ok -> cleanup
    print("{0} >= ? {1} -> {2}".format(time.time() - time_start+2 , 60*config['subexp_duration'], time.time() - time_start +2 >= 60 * config['subexp_duration'] is not True))
    cleanup_subexp(time.time() - time_start + 2 < 60 * config['subexp_duration'])


    print("nb seconds runtime: {0}".format(time.time() - time_start))
    print("nb threads = {0}".format(threading.active_count()))
   
   
    #kill all my children (including openweb server)
    if t_openwebserver is not None and t_openwebserver.is_alive():
        print("Cleanning up children process".format(t_openwebserver))
        process = psutil.Process(os.getpid())
        for proc in process.children(recursive=True):
            print("killing {0}".format(proc))
            proc.kill()
            print("..killed")



#starts a sequence of experiments, with a variable nb of nodes
def experiment_running_sequence(config):
         
    #selects the nodes
    for nbnodes in [12]:
        config['nb_nodes'] = nbnodes
        
        print("---- {0} nodes".format(nbnodes))
        if config['board']=="iot-lab_M3":
            config = nodes_selection(config, nbnodes)
        
        #application period
        config['cexampleperiod'] = 500 * nbnodes


        #reservation of the experiments
        if config['board']=="iot-lab_M3":
            config['exp_id'] = experiment_reservation(config)
        else:
            config['exp_id'] = 0

        # test the two different solutions
        #for anycast in [False , True]:
        for anycast in [True, False]:
            time_start = time.time()
            
            #param
            config['anycast'] = anycast
            print_header("anycast={0}, nbnodes={1}".format(anycast, nbnodes))

            experiment_execute(config)
            
            print("nb seconds runtime for this experiment: {0}".format(time.time() - time_start))

        #stop the experiment
        iotlabowsn.exp_stop(config['exp_id'])
        time.sleep(4.0)


#starts one fixed experiment for fault tolerance
def experiment_running_faulttolerance(config):
         
    #fixed scenario for fault tolerance
    config['nodes_list']=[ 332 , 346, 358 ]
    config['dagroots_list']=[ 316 ]
    nbnodes = len(config['nodes_list']) + len (config['dagroots_list'])

    #TODO: discard forbidden nodes (eg. 331)

    #application period
    config['cexampleperiod'] = 1000

    #reservation of the experiments
    config['exp_id'] = experiment_reservation(config)

    # test the two different solutions
    #for anycast in [False , True]:
    for anycast in [False, True]:
        time_start = time.time()
        
        #param
        config['anycast'] = anycast
        print_header("anycast={0}, nbnodes={1}".format(anycast, nbnodes))

        experiment_execute(config)
        
        print("nb seconds runtime for this experiment: {0}".format(time.time() - time_start))

    #stop the experiment
    iotlabowsn.exp_stop(config['exp_id'])
    time.sleep(4.0)





#main (multithreading safe)
if __name__ == "__main__":

     #----- INIT

    print_header("Initialization")
    iotlabowsn.root_verif()
    iotlabowsn.ip6table_install()
    config = configuration_set()
    config['seed'] = int(time.time()) #1
    random.seed(config['seed'])


    #openvisualizer
    # iotlabowsn.openvisualizer_install(config)
    # iotlabowsn.coap_install(config)

    #Parameters for this set of experiments
    config['badmaxrssi'] = -100
    config['goodminrssi'] = -100
    config['lowestrankfirst'] = 1


    #replay the same values 5 times
    for counter in range(5):
        #experiment_running_faulttolerance(config)
        experiment_running_sequence(config)

    #if we are here, this means that the collection of experiments is finished
    print("End of the computation")
    print("nb threads = {0}".format(threading.active_count()))

    sys.exit(0)




#NB: to disable icmpv6 unreachable (when coap packets cannot be delivered outside)
#ip6tables -I OUTPUT -p icmpv6  -j DROP
