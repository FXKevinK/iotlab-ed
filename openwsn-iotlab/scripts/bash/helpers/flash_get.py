# parses JSON reply, and identifies the experiment id 

import json, sys

#debug
if len(sys.argv) != 2:
    sys.exit("expid_last_get.py requires an argumnet (the json file), given: {0}".format(sys.argv))

with open(sys.argv[1], "r") as readfile:
    infos=json.load(readfile)

#pick the result for each name in the list
if "0" in infos:
    for info in infos["0"]:
        print("{0}: ok".format(info))

if "1" in infos:
    for info in infos["1"]:
        print("{0}: ko".format(info))
