#!/bin/bash



# saves the current directory to come back later here if needed
REP_CURRENT=`pwd`
temp_dir=$(mktemp -d)
echo "directory for temporary files: $temp_dir"



#compilation & firmwares
SW_SRC="../../openvisualizer"
#SW_GIT_VERSION="d3fa9b6"
FW_SRC="../../openwsn-fw"
#FW_GIT_VERSION="c96e335a"
FW_BIN="build/iot-lab_M3_armgcc/projects/common/03oos_openwsn_prog"
FW_BIN_IOTLAB="A8/03oos_openwsn_prog"


#----- git versions verification
#git rev-parse --short HEAD
if [ -n "$SW_GIT_VERSION" ]
then
    cd $SW_SRC
    if [ "`git rev-parse --short HEAD`" != "$SW_GIT_VERSION" ]
    then
        echo "the git version for software is not the right one"
        echo "REAL: `git rev-parse --short HEAD`"
        echo "EXPECTED: $SW_GIT_VERSION"
        exit 4
    fi
fi
cd $REP_CURRENT
if [ -n "$FW_GIT_VERSION" ]
then
    cd $FW_SRC
    if [ "`git rev-parse --short HEAD`" != "$FW_GIT_VERSION" ]
    then
        echo "the git version for firmware is not the right one"
        echo "REAL: `git rev-parse --short HEAD`"
            echo "EXPECTED: $FW_GIT_VERSION"
        exit 4
    fi
fi
cd $REP_CURRENT


#parameters for experiments
USER=theoleyr
NAME="owsn-cca"
NBNODES=3
DURATION=180


# choice for the architecture
# ------- m3 nodes (FIT IoTLab)
BOARD="iot-lab_M3"
TOOLCHAIN="armgcc"
ARCHI="m3"
SITE=grenoble
NODES_LIST="213+223"  # corner
DAGROOT="204"
#204+222+244 (milieu)
#193+203+211  (corner)
#94+99+127  (gauche toute)
# ------- A8 nodes (FIT IoTLab)
#BOARD="iot-lab_A8-M3"
#TOOLCHAIN="armgcc"
#ARCHI="a8"
#NODES_LIST="357+347+337"
#SITE=strasbourg
#------ Simulation
#BOARD="python"
#TOOLCHAIN="gcc"
#TOPOLOGY="--load-topology $REP_CURRENT/topologies/topology-3nodes.json"
#fast discovery (does it work?)
#OPTION="stackcfg=channel:18"
COMPIL_OPTIONS="boardopt=printf modules=coap,udp apps=cjoin,cexample scheduleopt=anycast,lowestrankfirst debugopt=CCA,schedule stackcfg=badmaxrssi:100,goodminrssi:100"  # be careful for simulations -> rssi values are incorrect

echo
echo
echo




# Check if we're root and re-execute if we're not.
#[ `whoami` = root ] || { sudo "$0" "$@"; exit $?; }



#Compilation
echo "------- Compilation ------"


echo " Compiling firmware..."
echo "Directory $FW_SRC"
cd $REP_CURRENT
cd $FW_SRC
CMD="scons -j4 board=$BOARD toolchain=$TOOLCHAIN $COMPIL_OPTIONS oos_openwsn"
echo $CMD
$CMD
#errors
if [ $? -ne 0 ]
then
echo "Compilation error (device)"
exit 6
fi



echo
echo
echo



if [[ "$BOARD" == "iot-lab"* ]]
then
   echo "----- search for an existing running experiment -------"
   cd $REP_CURRENT
   CMD="iotlab-experiment get -e"
   tmpfileExp="$temp_dir/json-exp.dump"
   $CMD > $tmpfileExp 2> /dev/null
   #cat json.dump
   EXPID=`python helpers/expid_last_get.py $tmpfileExp 2> /dev/null | cut -d "." -f 1 | cut -d "-" -f 2`
   if [ -z "$EXPID" ]
   then
      echo "No already experiment running"
   else
      echo "We found the experiment id: '$EXPID'"
   fi
   echo
   echo
   echo

   if [ -z	"$EXPID" ]
   then

      echo "----- reserve one experiment -------"
      if [ -z "$NODES_LIST" ]
      then
         CMD="iotlab-experiment submit -n $NAME -d $DURATION -l $NBNODES,archi=$ARCHI:at86rf231+site=$SITE"
      else
         CMD="iotlab-experiment submit -n $NAME -d $DURATION -l $SITE,$ARCHI,$NODES_LIST+$DAGROOT"
      fi
      echo $CMD
      RES=`$CMD`
      if [ $? -ne 0 ]
      then
         echo "the job submission has failed"
         exit 2
      fi
      EXPID=`echo $RES | grep id | cut -d ":" -f 2 | cut -d "}" -f 1`
      echo "ExperimentId=$EXPID"
      echo
      echo
      echo

   fi



   #wait the experiment starts runing
   echo "----- wait that the experiment is in running mode -------"
   cd $REP_CURRENT
   iotlab-experiment wait -i $EXPID
   echo
   echo
   echo


   #get the correct site
   echo "----- Site Identification -------"
   cd $REP_CURRENT
   CMD="iotlab-experiment get -i $EXPID -n"
   echo $CMD
   tmpfileSite="$temp_dir/json-site.dump"
   $CMD > $tmpfileSite
   SITE=`python helpers/site_get.py $tmpfileSite | cut -d "." -f 1 | cut -d "-" -f 2 `
   echo $SITE
   if [ -z "$SITE" ]
   then
      exit 5
   fi
   echo
   echo
   echo


   #EXperiment Identification
   #get the list of nodes
   echo "----- Nodes Identification -------"
   cd $REP_CURRENT
   NODES_LIST=`python helpers/nodes_list.py $tmpfileSite | cut -d "." -f 1 | cut -d "-" -f 2 | sort -g `
   echo "the nodes have been identified to"
   echo "$NODES_LIST"
   echo
   echo
   echo


   #transform the list of nodes in an array
   nbnodes=0
   for N in $NODES_LIST
   do
       NODES[$nbnodes]=$N
       ((nbnodes++))
   done
   echo "$nbnodes nodes"



   # A8 boot
   if [ "$ARCHI" == "a8" ]
   then
       echo "------- Wait that a8 nodes boot ------"
       iotlab-ssh wait-for-boot
   fi



   # FLASHING
   echo "------- Flash the devices ------"
   cd $REP_CURRENT
   cd $FW_SRC


   #flash the motes
   i=0
   port=10000

   if [ $ARCHI == "m3" ]
   then
       CMD="iotlab-node --flash $FW_BIN -i $EXPID"
       #by default, all the nodes, no need to specify the exhaustive list
       #NB: same firmware for all the nodes. One will be slected at runtime as dagroot
       #-l $SITE,$ARCHI,${NODES[$i]}"
   elif [ "$ARCHI" == "a8" ]
   then
       CMD="iotlab-ssh -i $EXPID --verbose run-cmd \"flash_a8_m3 $FW_BIN_IOTLAB\"
       echo "be careful, not tested with the novel cli tools, remove the next "exit()" to test it"
       exit
       #-l $SITE,$ARCHI,${NODES[$i]}"
   else
      echo "Unknown architecture:  $ARCHI"
      exit 4
   fi



   #flash command
   tmpfileFlash="$temp_dir/json-flash.dump"
   echo $CMD
   $CMD > $tmpfileFlash
       

   #parse the results for the flash command
   REP=`pwd`
   cd $REP_CURRENT
   RESULT=`python helpers/flash_get.py $tmpfileFlash`
   ERROR=`echo $RESULT | grep ko`
   OK=`echo $RESULT | grep ok`
   cd $REP
   echo "$OK" | tr " " "\n"
   #tmp file
   cat $tmpfileFlash
   echo
   echo

fi


# OpenViz server
echo "----- OpenVisualizer ------"
cd $REP_CURRENT
cd $SW_SRC

echo "install the current version of Openvisualizer"
CMD="pip2 install -e ."
echo $CMD
$CMD > /dev/null

#with opentun and -d for wireshark debug
# ------- FIT IOTLAB -----
cd $REP_CURRENT
OPENVIS_OPTIONS="--opentun --wireshark-debug --mqtt-broker 127.0.0.1 -d --fw-path /home/theoleyre/openwsn/openwsn-fw --lconf $REP_CURRENT/loggers/logging.conf"
if [[ "$BOARD" == "iot-lab"* ]]
then
   echo ""
   echo "Starts Openvisualizer (server part)"
   CMD="openv-server $OPENVIS_OPTIONS --iotlab-motes "
   MAX=`expr $nbnodes - 1`
   for i in `seq 0 $MAX`;
   do
           CMD="$CMD $ARCHI-${NODES[$i]}.$SITE.iot-lab.info"
   done
   #run in background
   CMD="$CMD"
# ------- SIMULATION
elif [[ "$BOARD" == "python" ]]
then
   echo ""
   echo "Starts Openvisualizer (server part)"
   CMD="openv-server $OPENVIS_OPTIONS --sim $NBNODES $TOPOLOGY"
   
# --------- BUG
else
   echo "Unknown board"
   exit 5
fi


echo $CMD
$CMD &
PID_OPENVSERVER=$!
echo "PID of openv-server to kill when the program exits: $PID_OPENVSERVER"



#let the server start
while [ -n "`openv-client motes | grep refused`" ]
do
    sleep 1    
    if [ -n "$PID_OPENVSERVER" -a -e /proc/$PID_OPENVSERVER ]
    then
        echo "openv-server not yet started"
    else
        echo "openv-server has stopped (critical)"
        exit 4
    fi
done



# ------- FIT IOTLAB -----
cd $REP_CURRENT
if [[ "$BOARD" == "iot-lab"* ]]
then
   echo "----- Force the reboot of the motes ------"
   CMD="iotlab-node --reset -i $EXPID"
   echo $CMD
   $CMD
fi





#----------  OpenV client -------
echo "----- Config after boot ------"
cd $REP_CURRENT
# --------- IOTLAB
if [[ "$BOARD" == "iot-lab"* ]]
then
   sleep 3
   CODERET=2
   while [ $CODERET -ne "0" ]
   do
       echo "openv-client motes | grep Ok | cut -d '|' -f 3 | grep $DAGROOT"
       MOTENAME=`openv-client motes | grep Ok | cut -d '|' -f 3 | grep $DAGROOT`
       
       if [ -z "$MOTENAME" ]
       then
            echo "the dagroot ($DAGROOT) is not part of the nodes' list"
            exit 5
       fi
       
       echo "setting mote '$MOTENAME' as dagroot"
       CMD="openv-client root $MOTENAME"
       echo $CMD
       $CMD
       CODERET=$?
       
       if [ $CODERET -ne "0" ]
       then
            echo "dagroot set: failed, retry"
       fi
    done
# ------- SIMULATION
# nothing to do: dagroot already selected
elif [[ "$BOARD" == "python" ]]
then
   echo "dagroot already selected automatically (first mote = 001)"
# --------- BUG
else
   echo "Unknown board"
   exit 5
fi



#server still running?
if [ -n "$PID_OPENVSERVER" -a -e /proc/$PID_OPENVSERVER ];
then
    #web interface (without a log message every time I receive a web request!)
    CMD="openv-client view web --debug ERROR"
    echo $CMD
    $CMD
    
    # kill the server part
    echo "----- Stops openv-server ------"
    echo "kill openv-server (pid=$PID_OPENVSERVER)"
    CMD="kill -SIGKILL $PID_OPENVSERVER"
    echo $CMD
    $CMD
fi


# flush temp files
echo "--- Cleanup ----"
echo "remove temporary files in directory $temp_dir"
rm -Rf $temp_dir

#end
#iotlab-experiment stop -i $EXPID

