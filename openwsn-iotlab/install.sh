#!/bin/bash

REPO_FW=https://github.com/ftheoleyre/openwsn-fw.git
REPO_SW=https://github.com/ftheoleyre/openvisualizer.git
REPO_COAP=https://github.com/openwsn-berkeley/coap.git
REPO_MQTT=https://github.com/eclipse/paho.mqtt.python
REPO_DATA=https://github.com/ftheoleyre/openwsn-data.git




# Current repository
REP=`pwd`



# ------- PYTHON & COMPILATION -----------



#Install Python
echo "------------------------"
echo "Installing Tools"
sudo apt-get install socat scons cmake



#Install Python
echo "------------------------"
echo "Installing Python"

echo "Install Python3/pip -- default version for the system"
sudo apt-get install virtualenvwrapper python3 python3-dev python3-pip  libssh2.1-dev libssl-dev
sudo update-alternatives --install /usr/bin/python python /usr/bin/python2.7 10



# Packages
echo "------------------------"
echo "Installing arm"
cd $REP
sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib

#echo "removing older gcc-arm 4_9-2014q4"
#rm -Rf gcc-arm-none-eabi-4_9-2014q4*
#wget gcc-arm-none-eabi-4_9-2014q4-20141203-linux.tar.bz2 https://launchpad.net/gcc-arm-embedded/4.9/4.9-2015-q3-update/+download/gcc-arm-none-eabi-4_9-2015q3-20150921-linux.tar.bz2
#bunzip2 gcc-arm-none-eabi-4_9-2014q4-20141203-linux.tar.bz2
#tar -xvf gcc-arm-none-eabi-4_9-2015q3-20150921-linux.tar
#rm gcc-arm-none-eabi-4_9-2015q3-20150921-linux.tar
#sudo rm -Rf gcc-arm-none-eabi
#mv gcc-arm-none-eabi-4_9-2014q4 gcc-arm-none-eabi
#echo "#ARM GCC" >> $HOME/.bashrc
#echo "PATH=$PATH:$HOME/openwsn/gcc-arm-none-eabi/bin" >> $HOME/.bashrc






# ------- IOT-Lab SPECIFIC -----------


#Install Cli Tools
echo "---------------------------------------------"
echo "Installing IoTLab Clitools (commands)"
sudo rm -Rf cli-tools
git clone https://github.com/iot-lab/cli-tools.git
cd cli-tools
sudo python setup.py install




# iotlab ssh tools
echo "-------------------------------"
echo "Installing IoTLab Clitools (ssh)"
cd $REP
sudo rm -Rf ssh-cli-tools
git clone https://github.com/iot-lab/ssh-cli-tools.git
cd ssh-cli-tools
sudo apt-get install virtualenvwrapper
sudo pip install .



# ------- OPENWSN SPECIFIC -----------

# Firmware
echo "------------------------"
echo "Clonning Firmware"
cd $REP
sudo rm -Rf openwsn-fw
git clone $REPO_FW



# CoAP
echo "------------------------"
echo "Installing CoAP option"
cd $REP
sudo rm -rf coap
git clone $REPO_COAP




# Packages
# Software tools
echo "-------------------------------------------------"
echo "Cloning openvisualizer tools and dependencies"
cd $REP
sudo rm -Rf openvisualizer
git clone $REPO_SW
cd openvisualizer
sudo pip install -r requirements.txt
sudo pip install -e .
cd $REP
sudo rm -rf paho.mqtt.python
git clone $REPO_MQTT
cd paho.mqtt.python
sudo python setup.py install




# ------- OPENWSN DATA Analysis -----------

echo "-------------------------------------------------"
echo "installing conda"
cd $REP
sudo apt-get install libgl1-mesa-glx libegl1-mesa libxrandr2 libxrandr2 libxss1 libxcursor1 libxcomposite1 libasound2 libxi6 libxtst6 curl
curl -O https://repo.anaconda.com/archive/Anaconda3-2021.05-Linux-x86_64.sh
chmod u+x Anaconda3-2021.05-Linux-x86_64.sh
./Anaconda3-2021.05-Linux-x86_64.sh
./anaconda3/bin/conda init zsh
conda update conda


echo "-------------------------------------------------"
echo "Cloning openwsn-data"
cd $REP
git clone $REPO_DATA
cd openwsn-data
conda env create -f openwsn-data.yml







echo "-------------------------------------------------"
echo "REQ"


echo "You have still to register your iotlab credentials with the command"
echo "iotlab-auth -u $USER -p PASSWORD"
echo "and test everything with scripts/start_and_flash.sh"

