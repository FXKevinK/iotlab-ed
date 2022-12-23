#list the nodes from a JSON and translate them into a list of net addresses

import json, sys

#debug
if len(sys.argv) != 2:
    sys.exit("expid_last_get.py requires an argumnet (the json file), given: {0}".format(sys.argv))

with open(sys.argv[1], "r") as readfile:
    nodes=json.load(readfile)
#print(nodes)

#pick the network address
for node in nodes["items"]:
    print(node["network_address"])
