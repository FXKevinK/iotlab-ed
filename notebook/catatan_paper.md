# Terkait paper:
- taruh penjelasan dan pembeda tentang adaptive epsilon
- ubah flowchart pake adaptive epsilon

# Parameter:
Topologies: 10 (5*2), 35 (5*7)
OS: OpenWSN, Board: Arm M3 Cortex
Slot duration: 10 ms, Slotframe length: 101
Duration: 60minutes x 3
Channel: 16
Testbed: Fit IoT-LAb Lille
Runtime: 60 minutes
M: 8
K_max: 10 (since all algo adaptive k)
Packet 20bytes/second (Agriculture monitoring)

# Control variable:
Learning and Discount rate: 0.2, 0.5, 0.8
Epsilon decay rate: 0.01, 0.05, 0.1
Epsilon static: 0.2, 0.5, 0.8
Number of nodes: Sim 10,50,100 Test 10,35
Imin: 1s, 5s, 10s

# Metrics:
MBR: Bar
Joining time: CDF
Energy consumption: Total Bar
-Second tier metric
Reward & Epsilon: Line incremental (qlearning convergence)
DIO Transmission, Supression, Failed Transmission
PDR: Bar
Latency: Bar

# Scenario:
1. Evaluation qlearning parameter (and convergence) only qtrickle
<!-- Use Default: Node 50, AppPeriod 0, a/b/e 0.5, imin 5s -->
- Learning & Discont rate: 3 axis (pfree, Joining time, Energy consumption) over 9 (learning x discont rate) with best epsilon decay rate: **0.2 & 0.5**
- Epsilon: 3 axis (pfree, Joining time, Energy consumption) over 6 epsilon (decay & static): **0.05**
- Qtrickle convergence (initialization into later): 4 axis (Pfree, Epsilon, K, ListenPeriod) over Trickle State (Line chart) with best aplha, betha, epsilon decay (random 1 parent node)

2. Evaluation network parameter (4 algo: ori, qt, riata, ac)
- Number of Nodes & Minimum Interval (over 9x4, 3 nodes x 3 interval x 4 algo):
- - 3 Bar (pfree, Joining time, Energy consumption) 9x4
- - Table count DIO Transmission, Supression, Failed Transmission

4. Evaluation on Testbed (with packet transmission): 2 algo (or & qt)
- Main metric: 3 CDF (Pfree, Joining time, Energy consumption) over 4 (2 nodes x 2 algo)
- Packet transmission: 2 Bar (PDR & Latency) over 4
- Computational: 2 value table of Firmware size & runtime excluding waiting per interval. over 4
- Add/Remove node: Select random 20% of the node: 7 of large topology only 
(a) Turn off in the beginning and then after 30minutes turn on to emulate Add. (b) Turn off after 30minutes to emulate Remove.
- - 4 axis (Pfree, DIOTransmit, K, ListenPeriod) over ASN over 4 (algo and condition add/remove) of random 1 parent node, give middle line indicate add/remove process.


<!-- Remove .git -->
( find . -type d -name ".git" ) | xargs rm -rf
<!-- Remove .DS_Store -->
( find . -type f -name ".DS_Store" ) | xargs rm -rf

openv-server --sim=2 --simtopo=linear

cd openwsn-fw; scons board=python toolchain=gcc modules=icmpv6periodic oos_openwsn; cd ..

cd openwsn-fw; scons board=iot-lab_M3 toolchain=armgcc modules=icmpv6periodic oos_openwsn; cd ..

pscp -i ~/.ssh/id_rsa.ppk dfawwaz@saclay.iot-lab.info:A8/03oos_openwsn_prog .

export PATH=$PATH:/opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin

allow more exploration in beginning, because ql need learn.
allow more exploitation when reward converge. when fluctuate allow more exploration (to adapt).


python3.7 runSim.py --config config_1.json;

python3.7 compute_kpis.py;

====================

<!-- exp 1 -->
python3.7 runSim.py --algo=qt_1 --param_lr=0.5 --param_dr=0.1;
python3.7 runSim.py --algo=qt_1 --param_lr=0.5 --param_dr=0.3;
python3.7 runSim.py --algo=qt_1 --param_lr=0.5 --param_dr=0.5;
python3.7 runSim.py --algo=qt_1 --param_lr=0.5 --param_dr=0.7;
python3.7 runSim.py --algo=qt_1 --param_lr=0.5 --param_dr=0.9;

<!-- exp 2 -->

python3.7 runSim.py --algo=qt_2 --param_lr=0.1 --param_dr=0.5;
python3.7 runSim.py --algo=qt_2 --param_lr=0.3 --param_dr=0.5;
python3.7 runSim.py --algo=qt_2 --param_lr=0.5 --param_dr=0.5;
python3.7 runSim.py --algo=qt_2 --param_lr=0.7 --param_dr=0.5;
python3.7 runSim.py --algo=qt_2 --param_lr=0.9 --param_dr=0.5;

<!-- exp 3 -->
python3.7 runSim.py --algo=qt_3 --param_ep=0.1 --param_ad=0;
python3.7 runSim.py --algo=qt_3 --param_ep=0.3 --param_ad=0;
python3.7 runSim.py --algo=qt_3 --param_ep=0.5 --param_ad=0;
python3.7 runSim.py --algo=qt_3 --param_ep=0.7 --param_ad=0;
python3.7 runSim.py --algo=qt_3 --param_ep=0.9 --param_ad=0;

python3.7 runSim.py --algo=qt_3 --param_epdecay=0.001 --param_ad=1;
python3.7 runSim.py --algo=qt_3 --param_epdecay=0.01 --param_ad=1;
python3.7 runSim.py --algo=qt_3 --param_epdecay=0.05 --param_ad=1;
python3.7 runSim.py --algo=qt_3 --param_epdecay=0.1 --param_ad=1;
python3.7 runSim.py --algo=qt_3 --param_epdecay=0.2 --param_ad=1;
python3.7 runSim.py --algo=qt_3 --param_epdecay=0.3 --param_ad=1;

<!-- exp 5 Add/Remove-->
python3.7 runSim.py --algo=qt_4 --param_addrem=1;
python3.7 runSim.py --algo=qt_4 --param_addrem=2;

python3.7 runSim.py --algo=ori --param_addrem=1;
python3.7 runSim.py --algo=ori --param_addrem=2;

python3.7 runSim.py --algo=riata --param_addrem=1;
python3.7 runSim.py --algo=riata --param_addrem=2;

python3.7 runSim.py --algo=ac --param_addrem=1;
python3.7 runSim.py --algo=ac --param_addrem=2;

<!-- exp 4 -->
python3.7 runSim.py --algo=ori --param_motes=10 --param_imin=1;
python3.7 runSim.py --algo=ori --param_motes=10 --param_imin=5;
python3.7 runSim.py --algo=ori --param_motes=10 --param_imin=10;

python3.7 runSim.py --algo=ori --param_motes=50 --param_imin=1;
python3.7 runSim.py --algo=ori --param_motes=50 --param_imin=5;
python3.7 runSim.py --algo=ori --param_motes=50 --param_imin=10;

python3.7 runSim.py --algo=ori --param_motes=100 --param_imin=1;
python3.7 runSim.py --algo=ori --param_motes=100 --param_imin=5;
python3.7 runSim.py --algo=ori --param_motes=100 --param_imin=10;

python3.7 runSim.py --algo=riata --param_motes=10 --param_imin=1;
python3.7 runSim.py --algo=riata --param_motes=10 --param_imin=5;
python3.7 runSim.py --algo=riata --param_motes=10 --param_imin=10;

python3.7 runSim.py --algo=riata --param_motes=50 --param_imin=1;
python3.7 runSim.py --algo=riata --param_motes=50 --param_imin=5;
python3.7 runSim.py --algo=riata --param_motes=50 --param_imin=10;

python3.7 runSim.py --algo=riata --param_motes=100 --param_imin=1;
python3.7 runSim.py --algo=riata --param_motes=100 --param_imin=5;
python3.7 runSim.py --algo=riata --param_motes=100 --param_imin=10;


python3.7 runSim.py --algo=ac --param_motes=10 --param_imin=1;
python3.7 runSim.py --algo=ac --param_motes=10 --param_imin=5;
python3.7 runSim.py --algo=ac --param_motes=10 --param_imin=10;

python3.7 runSim.py --algo=ac --param_motes=50 --param_imin=1;
python3.7 runSim.py --algo=ac --param_motes=50 --param_imin=5;
python3.7 runSim.py --algo=ac --param_motes=50 --param_imin=10;

python3.7 runSim.py --algo=ac --param_motes=100 --param_imin=1;
python3.7 runSim.py --algo=ac --param_motes=100 --param_imin=5;
python3.7 runSim.py --algo=ac --param_motes=100 --param_imin=10;

python3.7 runSim.py --algo=qt_4 --param_motes=10 --param_imin=1;
python3.7 runSim.py --algo=qt_4 --param_motes=50 --param_imin=1;

python3.7 runSim.py --algo=qt_4 --param_motes=10 --param_imin=5;
python3.7 runSim.py --algo=qt_4 --param_motes=50 --param_imin=5;

python3.7 runSim.py --algo=qt_4 --param_motes=10 --param_imin=10;
python3.7 runSim.py --algo=qt_4 --param_motes=50 --param_imin=10;

python3.7 runSim.py --algo=qt_4 --param_motes=100 --param_imin=1;
python3.7 runSim.py --algo=qt_4 --param_motes=100 --param_imin=5;
python3.7 runSim.py --algo=qt_4 --param_motes=100 --param_imin=10;
