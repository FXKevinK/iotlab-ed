#!/usr/bin/env python3
# coding: utf-8


#files
import subprocess

# format
import string
import json
import array

# multiprocess
import threading
import psutil

#systems
import os
import sys
import sys
import time

from queue import Queue, Empty


# ----- Transfer stdout and stderr in a queue ---

def reader(proc, pipe, queue):
    print("{0}/{1}: process started".format(proc, pipe))

    while True:
        try:
            line = pipe.readline()
            queue.put((pipe, line))
            
            if proc.poll() is not None:
                print("{0}/{1}: process terminated".format(proc, pipe))
                queue.put(None)
                return
                
        except:
            print("error reader() {0}".format(sys.exc_info()[0]))
            print(proc.poll())
 
    print("end of reader()")

        

#Run an extern command and returns the stdout
def run_command_printrealtime(cmd, path=None, timeout=None):
    
    print("CMD: {0}".format(cmd))
    process = subprocess.Popen(cmd, shell=True, stdin=open(os.devnull), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=path, close_fds=True, universal_newlines=True, bufsize=0)

    #queue for stdout + stderr
    q = Queue()
    
    t_stdout = threading.Thread(target=reader, args=(process, process.stdout, q))
    t_stdout.daemon = True # thread dies with the program
    t_stdout.start()
    
    t_stderr = threading.Thread(target=reader, args=(process, process.stderr, q))
    t_stderr.daemon = True # thread dies with the program
    t_stderr.start()

    start_time = time.time()
    
  # for _ in range(2):
    while True:
        try:
            source, line = q.get_nowait() # or q.get(timeout=.1)
        
        except Empty:
            time.sleep(0.1)
            
        #process terminated
        except TypeError:
            break;
        
        except:
            print("No running experiment, error {0}".format(sys.exc_info()[0]))

        else:
            print("{0}".format(line.rstrip()))
            #print("{0}: {1}".format(source, line.rstrip()))

  
        #timeout
        if (timeout is not None) and (time.time() - start_time > timeout):
            
            #kill shell process + its children
            if process.poll() is None:
                print("to kill")
            
                process_shell = psutil.Process(process.pid)
                for proc in process_shell.children(recursive=True):
                    print("killing {0}".format(proc))
                    proc.kill()
                    print("..killed")
                process_shell.kill()
            
            print("command has timeouted")
            break
        #elif (timeout is not None):
        #    print("{0}  < {1}".format(time.time() - start_time, timeout))
            
                
    out = "not handled in printrealtime"
    err = "not handled in printrealtime"
    return(process, out, err)



#Run an extern command and returns the stdout
def run_command(cmd, path=None, timeout=None):

    process = subprocess.run(cmd, shell=True, cwd=path, close_fds=True, timeout=timeout, capture_output=True, text=True)

    out = process.stdout
    err = process.stderr
    
    return(process, out, err)
    

#sudo verification
def root_verif():
    if (os.getuid() != 0):
        print("\n\n---------------------------------------------")
        print("      Error")
        print("---------------------------------------------\n\n")

        print("You must be root to run this script")
        print("{0} != 0".format(os.getuid()))
        sys.exit(2)


#ipv6 rules
def ip6table_install():
    CMD="sudo ip6tables -S | grep \"ipv6-icmp -j DROP\""
    process,out, err = run_command(CMD)
    if (out.find("-A OUTPUT -p") != -1):
        print("IPV6 table rule already exists for ICMPv6 packets")
    else:
        CMD="sudo ip6tables -A OUTPUT -p icmpv6  -j DROP"
        print(CMD)
        process,out, err = run_command(CMD)
        print("IPV6 table rule inserted for ICMPv6 packets")
    
    print("")
#sudo ip6tables -D  OUTPUT -p icmpv6  -j DROP

#----- Experiments control


#compiles a firmware
def compilation_firmware(config):
    
    cmd="scons board=" + config['board'] + " toolchain=" + config['toolchain'] + " "
    #cmd=cmd +" modules=coap,udp apps=cexample debugopt=CCA,schedule,sixtop,MSF logging=1"
    cmd=cmd +" boardopt=printf modules=coap,udp apps=cexample debugopt=CCA,schedule,sixtop,MSF "
    if (config['anycast'] and config['lowestrankfirst']):
        cmd=cmd + " scheduleopt=anycast,lowestrankfirst "
    elif (config['anycast']):
        cmd=cmd + " scheduleopt=anycast "
    cmd=cmd + " stackcfg=adaptive-msf,cexampleperiod:"+str(config['cexampleperiod'])+",badmaxrssi:"+str(config['badmaxrssi'])+",goodminrssi:"+str(config['goodminrssi']) + " "
    cmd=cmd + " oos_openwsn "

    process, out, err = run_command_printrealtime(cmd=cmd, path=config['code_fw_src'])

    if (process.returncode != 0):
        print("Compilation has failed")
        sys.exit(-5)


# get the iotlab id for a runnning experiment (to resume it)
def get_running_id(config):
    cmd = 'iotlab-experiment get -e'
    process,output,err = run_command(cmd=cmd)
    infos = json.loads(output)

    # pick the last (most recent) experiment
    try:
        exp_id_running=infos["Running"][-1]
        
        #Site identification (if the experiment is already running)
        cmd="iotlab-experiment get -i " + str(exp_id_running) + " -n"
        process,output,err = run_command(cmd=cmd)
        
        print("running experiment: {0}".format(exp_id_running))
    except KeyError:
        print("No running experiment")
        return
    except:
        print("No running experiment, error {0}".format(sys.exc_info()[0]))
        return
        #nothing returned
    
    #to verify that the experiment is matching with my params
    if config['exp_resume_verif'] :
        infos=json.loads(output)
        exp_site=infos["items"][0]["site"]
        if (config['site'] != exp_site):
            print("the site of the running experiment doesn't match: {0} != {1}".format(config['site'], exp_site))
        
        #nodes identification
        print("Verification that the list of nodes is correct for the exp_id {0}".format(exp_id_running))
        for node in infos["items"]:
            print("  -> {0}".format(node["network_address"]))
            sp = node["network_address"].split(".")
            sp2 = sp[0].split("-")
            node_id = int(sp2[1])
            if node_id not in config['dagroots_list']:
                if node_id not in config['nodes_list']:
                    print("     {0} is present neither in {1} nor in {2}".format(
                        sp2[1],
                        config['dagroots_list'],
                        config['nodes_list']
                    ))
                    return
                else:
                    print("     {0} is a node (in {1})".format(node_id, config['nodes_list']))
            else:
                print("     {0} is a dagroot (in {1})".format(node_id, config['dagroots_list']))

    #get the ids of the running exp
    else:
        config['nodes_list'].clear()
    
        infos=json.loads(output)
        exp_site=infos["items"][0]["site"]
        if (config['site'] != exp_site):
            print("the site of the running experiment doesn't match: {0} != {1}".format(config['site'], exp_site))
        
        #nodes identification
        for node in infos["items"]:
            print("  -> {0}".format(node["network_address"]))
            sp = node["network_address"].split(".")
            sp2 = sp[0].split("-")
            node_id = int(sp2[1])

            config['nodes_list'].append(node_id)

        #dagroot = first node
        config['nodes_list'].sort(key=int)
        config['dagroots_list'] = [config['nodes_list'][0], ]
        config['nodes_list'].remove(config['dagroots_list'][0])



    return(exp_id_running)


# start a novel experiment with the right config
def exp_start(config):
    exp_id_running=0
    cmd= "iotlab-experiment submit " + " -n "+config['exp_name']
    cmd=cmd + " -d "+ str(config['exp_duration'])
    cmd=cmd + " -l "+ config['site'] + "," + config['archi'] + ","
    for i in range(len(config['dagroots_list'])):
        if ( i != 0 ):
            cmd=cmd+"+"    
        cmd= cmd + str(config['dagroots_list'][i])
    for node in config['nodes_list'] :
        cmd= cmd + "+" + str(node)
    
    try:
        print(cmd)
        process,output,err = run_command(cmd=cmd)
        print(output)
        infos=json.loads(output)
        print(infos)
        exp_id_running=infos["id"]
        return(exp_id_running)
    except:
        return None
    

# waits that the id is running
def exp_wait_running(exp_id):
    cmd="iotlab-experiment wait -i "+ str(exp_id)
    process,output,err = run_command(cmd=cmd)
    print(output)

# waits that the id is running
def exp_stop(exp_id):
    cmd="iotlab-experiment stop -i "+ str(exp_id)
    process,output,err = run_command(cmd=cmd)
    print(output)


def get_nodes_list(site, archi, state):
    nodes_list = []
    
    cmd="iotlab-status --nodes --site "+site+" --archi "+archi+" --state "+state
    process,output,err = run_command(cmd=cmd)
    #print(out)
    print(err)
    infos=json.loads(output)
    l_net = infos["items"][0]["network_address"]
    for item in infos["items"]:
        node = item["network_address"].split('.')[0].split('-')[1]
        nodes_list.append(node)
    nodes_list.sort(key=int)
    return(nodes_list)
    
#Flashing the devices with a compiled firmware
def flashing_motes(exp_id, config):
    cmd="iotlab-node --flash " + config['code_fw_bin'] + " -i " + str(exp_id)
    process,output,err = run_command(cmd=cmd)
    infos=json.loads(output)
    ok=True
    if "0" in infos:
        for info in infos["0"]:
            print("{0}: ok".format(info))

    if "1" in infos:
        for info in infos["1"]:
            print("{0}: ko".format(info))
            ok = False
    if ( ok == False ):
        print("Some motes have not been flashed correctly, stop now")
        exit(6)




#install the last version of OV (present in the code_sw_src directory
def openvisualizer_install(config):
    print("Install the current version of Openvisualizer")
    cmd="pip2 install -e ."
    process,output,err = run_command(cmd=cmd, path=config['code_sw_src'])
    print(err)
    
    if (process.returncode != 0):
        print("Installation of openvisualizer has failed")
        exit(-7)
    else:
        print("Installation ok")


#install the last version of coap
def coap_install(config):
    print("Install the current version of CoAP")
    cmd="pip2 install -e ."
    process,output,err = run_command(cmd=cmd, path=config['code_coap_src'])
    print(err)
    
    if (process.returncode != 0):
        print("Installation of coap has failed")
        exit(-7)
    else:
        print("Installation ok")


#generated the configuration file (for logging)
def openvisualizer_create_conf_file(config):
    #construct the config file
    file=open(config['conf_file'], 'w')
            
    # constant beginning
    file_start=open(config['conf_file_start'], 'r')
    for line in file_start:
        file.write(line)
    file_start.close()

    file.write("[handler_std]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server.log', 'w')\n")
    file.write("formatter=std\n\n")

    file.write("[handler_errors]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server-errors.log', 'w')\n")
    file.write("level=ERROR\n")
    file.write("formatter=std\n\n")

    file.write("[handler_success]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server-success.log', 'w')\n")
    file.write("level=SUCCESS\n")
    file.write("formatter=std\n\n")

    file.write("[handler_info]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server-info.log', 'w')\n")
    file.write("level=INFO\n")
    file.write("formatter=std\n\n")

    file.write("[handler_all]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server-all.log', 'w')\n")
    file.write("formatter=std\n\n")

    file.write("[handler_html]\n")
    file.write("class=logging.FileHandler\n")
    file.write("args=('"+config['path_results']+"/openv-server-all.html.log', 'w')\n")
    file.write("formatter=console\n\n")

    #constant end
    file_end=open(config['conf_file_end'], 'r')
    for line in file_end:
        file.write(line)
    file_end.close()

    #end of the config file
    file.close()




# starts the openvisualizer as a thread (returns only when it is in running mode)
def openvisualizer_start(config):

    #construct the command with all the options for openvisualizer
    openvisualizer_options="--opentun --wireshark-debug --mqtt-broker 127.0.0.1 -d --fw-path /home/theoleyre/openwsn/openwsn-fw"
    openvisualizer_options=openvisualizer_options+ " --lconf " + config['conf_file']
    if (config['board'] == "iot-lab_M3" ):
        cmd="python2 /usr/local/bin/openv-server " + openvisualizer_options + " --iotlab-motes "
        for i in range(len(config['dagroots_list'])):
            cmd=cmd + config['archi'] + "-" + str(config['dagroots_list'][i]) + "." + config['site'] + ".iot-lab.info "
        for i in range(len(config['nodes_list'])):
            cmd=cmd + config['archi'] + "-" + str(config['nodes_list'][i]) + "." + config['site'] + ".iot-lab.info "
    elif (config['board'] == "python" ):
        cmd="python2 /usr/local/bin/openv-server " + openvisualizer_options + " --sim "+ str(config['nb_nodes']) + " " + config['topology']

    # stops the previous process
    try:
        print("Previous process: {0}".format(process_openvisualizer))
        process_openvisualizer.terminate()
    except NameError:
        print("No running openvisualizer process")
    except:
        print("openvisualizer_start, No running openvisualizer process, error {0}".format(sys.exc_info()[0]))
        
    #Running the OV application
    print("Running openvisualizer in a separated process")
    t_openvisualizer = threading.Thread(target=run_command_printrealtime, args=(cmd,  config['code_sw_src'], config['subexp_duration'] * 60,))  #with real time print stdout/stderr
    t_openvisualizer.daemon = True
    t_openvisualizer.start()
    print("Thread {0} started".format(t_openvisualizer))

    return(t_openvisualizer)


#return the nb of motes attached to openvisualizer
def openvisualizer_nbmotes():

    cmd="openv-client motes"
    process,output,err = run_command(cmd=cmd)
    print("client: \n{0}".format(output))
    #print(output.find("Connection refused"))
        
    #connected -> openvisualizer is running
    if output.find("Connection refused") == -1:
        nbmotes = 0
        
        #count  the number of lines that contain an m3 mote
        for line in output.split('\n'):
            if line.find("m3") != -1 or line.find("emulated") != -1:
                nbmotes = nbmotes + 1
        return(nbmotes)

    else:
        return None
        
      

 

#start the web client part
def openwebserver_start(config):

    cmd="python2 /usr/local/bin/openv-client view web --debug ERROR"
    print("Running openweb server in a separated thread")
    t_openwebserver = threading.Thread(target=run_command, args=(cmd, config['code_sw_src'], ))    #no real time print stdout/stderr

    t_openwebserver.daemon = True
    t_openwebserver.start()
    print("Thread {0} started, pid {1}".format(t_openwebserver, os.getpid()))

    return(t_openwebserver)


#reboot all the motes (if some have been already selected dagroot for an unkwnon reason)
def mote_boot(exp_id):
    cmd="iotlab-node --reset -i "+ str(exp_id)
    run_command_printrealtime(cmd=cmd)




# Configuration: dagroot
def dagroot_set(config):
    for node in config['dagroots_list']:
        cmd="openv-client root m3-" + str(node) +  "." + config['site'] + ".iot-lab.info"
        process,out,err = run_command(cmd=cmd)
        
        print("out: {0}".format(out))
        print("err: {0}".format(err))


        if (out.find("Make sure the motes are booted and provide a 16B mote address or a port ID to set the DAG root") != -1):
            print("the dagroot configuration failed")
            return False
        return True






