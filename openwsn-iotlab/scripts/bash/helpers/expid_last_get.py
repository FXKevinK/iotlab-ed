# parses JSON reply, and identifies the experiment id 

import json, sys

#debug
if len(sys.argv) != 2:
    sys.exit("expid_last_get.py requires an argumnet (the json file), given: {0}".format(sys.argv))

with open(sys.argv[1], "r") as readfile:
    infos=json.load(readfile)
    
#pick the last (most recent) experiment
print(infos["Running"][-1])

