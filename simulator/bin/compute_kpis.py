from __future__ import division
from __future__ import print_function

# =========================== adjust path =====================================

import os
import sys
import argparse
from scipy.stats import skew, kurtosis
import pandas as pd
import netaddr

if __name__ == '__main__':
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..'))

# ========================== imports ==========================================

import json
import glob
import numpy as np

from SimEngine import SimLog
import SimEngine.Mote.MoteDefines as d

# =========================== defines =========================================

DAGROOT_ID = 0  # we assume first mote is DAGRoot
DAGROOT_IP = 'fd00::1:0'
BATTERY_AA_CAPACITY_mAh = 2821.5

# =========================== decorators ======================================


def openfile(func):
    def inner(inputfile):
        with open(inputfile, 'r') as f:
            return func(f)
    return inner

# =========================== helpers =========================================


def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)


def init_mote():
    return {
        'upstream_num_tx': 0,
        'upstream_num_rx': 0,
        'upstream_num_lost': 0,
        'join_asn': None,
        'join_time_m': None,
        'sync_asn': None,
        'sync_time_s': None,
        'charge_asn': None,
        'upstream_pkts': {},
        'latencies': [],
        'hops': [],
        'charge': None,
        'lifetime_AA_years': None,
        'avg_current_uA': None,
        'trickle': {},
    }

# =========================== KPIs ============================================


@openfile
def kpis_all(inputfile):

    allstats = {}  # indexed by run_id, mote_id

    # first line contains settings
    file_settings = json.loads(inputfile.readline())

    trickle_keys = []
    last_slotframe_keys = []

    # === gather raw stats

    for line in inputfile:
        logline = json.loads(line)

        # shorthands
        run_id = logline['_run_id']
        if '_asn' in logline:  # TODO this should be enforced in each line
            asn = logline['_asn']
        if '_mote_id' in logline:  # TODO this should be enforced in each line
            mote_id = logline['_mote_id']

        # populate
        if run_id not in allstats:
            allstats[run_id] = {}
        if (
            ('_mote_id' in logline)
            and
            (mote_id not in allstats[run_id])
            and
            (mote_id != DAGROOT_ID)
        ):
            allstats[run_id][mote_id] = init_mote()

        if logline['_type'] == SimLog.LOG_TSCH_SYNCED['type']:
            # sync'ed

            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot sync times
            if mote_id == DAGROOT_ID:
                continue

            allstats[run_id][mote_id]['sync_asn'] = asn
            allstats[run_id][mote_id]['sync_time_s'] = asn * \
                file_settings['tsch_slotDuration']

        elif logline['_type'] == SimLog.LOG_RPL_JOINED['type']:
            # joined

            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot join times
            if mote_id == DAGROOT_ID:
                continue

            # populate
            assert allstats[run_id][mote_id]['sync_asn'] is not None
            allstats[run_id][mote_id]['join_asn'] = asn
            allstats[run_id][mote_id]['join_time_m'] = asn * file_settings['tsch_slotDuration'] / 60

        elif logline['_type'] == SimLog.LOG_APP_TX['type']:
            # packet transmission

            # shorthands
            mote_id = logline['_mote_id']
            dstIp = logline['packet']['net']['dstIp']
            appcounter = logline['packet']['app']['appcounter']

            # only log upstream packets
            if dstIp != DAGROOT_IP:
                continue

            # populate
            assert allstats[run_id][mote_id]['join_asn'] is not None
            if appcounter not in allstats[run_id][mote_id]['upstream_pkts']:
                allstats[run_id][mote_id]['upstream_pkts'][appcounter] = {
                    'hops': 0,
                }

            allstats[run_id][mote_id]['upstream_pkts'][appcounter]['tx_asn'] = asn

        elif logline['_type'] == SimLog.LOG_APP_RX['type']:
            # packet reception

            # shorthands
            mote_id = netaddr.IPAddress(
                logline['packet']['net']['srcIp']).words[-1]
            dstIp = logline['packet']['net']['dstIp']
            hop_limit = logline['packet']['net']['hop_limit']
            appcounter = logline['packet']['app']['appcounter']

            # only log upstream packets
            if dstIp != DAGROOT_IP:
                continue

            allstats[run_id][mote_id]['upstream_pkts'][appcounter]['hops'] = (
                d.IPV6_DEFAULT_HOP_LIMIT - hop_limit + 1
            )
            allstats[run_id][mote_id]['upstream_pkts'][appcounter]['rx_asn'] = asn

        elif logline['_type'] == SimLog.LOG_LAST_SLOTFRAME['type']:
            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot
            if mote_id == DAGROOT_ID:
                continue
            
            for key in logline['result'].keys():
                if key not in last_slotframe_keys:
                    last_slotframe_keys.append(key)

                allstats[run_id][mote_id][key] = logline['result'][key]

        elif logline['_type'] == SimLog.LOG_TRICKLE['type']:
            # trickle result

            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot
            if mote_id == DAGROOT_ID:
                continue

            state = logline['result']['state']
            # populate
            if state not in allstats[run_id][mote_id]['trickle']:
                allstats[run_id][mote_id]['trickle'][state] = {}

            for key in logline['result'].keys():
                if key not in trickle_keys:
                    trickle_keys.append(key)

                value = logline['result'][key]
                allstats[run_id][mote_id]['trickle'][state][key] = value

        elif logline['_type'] == SimLog.LOG_RADIO_STATS['type']:
            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot charge
            if mote_id == DAGROOT_ID:
                continue

            charge = logline['idle_listen'] * d.CHARGE_IdleListen_uC
            charge += logline['tx_data_rx_ack'] * d.CHARGE_TxDataRxAck_uC
            charge += logline['rx_data_tx_ack'] * d.CHARGE_RxDataTxAck_uC
            charge += logline['tx_data'] * d.CHARGE_TxData_uC
            charge += logline['rx_data'] * d.CHARGE_RxData_uC
            charge += logline['sleep'] * d.CHARGE_Sleep_uC

            allstats[run_id][mote_id]['charge_asn'] = asn
            allstats[run_id][mote_id]['charge'] = charge

    # === compute advanced motestats

    for (run_id, per_mote_stats) in list(allstats.items()):
        for (mote_id, motestats) in list(per_mote_stats.items()):
            if mote_id != 0:

                if (motestats['sync_asn'] is not None) and (motestats['charge_asn'] is not None):
                    # avg_current, lifetime_AA
                    if (
                        (motestats['charge'] <= 0)
                        or
                        (motestats['charge_asn']
                         <= motestats['sync_asn'])
                    ):
                        motestats['lifetime_AA_years'] = 'N/A'
                    else:
                        # motestats['charge'] in millicoulombs
                        # motestats['avg_current_uA'] in mAs (seconds)
                        # 1 mAh = 1 * 3600 seconds
                        # 1 hour = 3600 seconds
                        # 1 mAs = mC
                        time = float((motestats['charge_asn']-motestats['sync_asn']) * file_settings['tsch_slotDuration'])
                        motestats['avg_current_uA'] = motestats['charge']/time
                        assert motestats['avg_current_uA'] > 0
                        motestats['lifetime_AA_years'] = (
                            BATTERY_AA_CAPACITY_mAh*1000/float(motestats['avg_current_uA']))/(24.0*365)
                if motestats['join_asn'] is not None:
                    # latencies, upstream_num_tx, upstream_num_rx, upstream_num_lost
                    for (appcounter, pktstats) in list(allstats[run_id][mote_id]['upstream_pkts'].items()):
                        motestats['upstream_num_tx'] += 1
                        if 'rx_asn' in pktstats:
                            motestats['upstream_num_rx'] += 1
                            thislatency = (
                                pktstats['rx_asn']-pktstats['tx_asn'])*file_settings['tsch_slotDuration']
                            motestats['latencies'] += [thislatency]
                            motestats['hops'] += [pktstats['hops']]
                        else:
                            motestats['upstream_num_lost'] += 1
                    if (motestats['upstream_num_rx'] > 0) and (motestats['upstream_num_tx'] > 0):
                        motestats['latency_min_s'] = min(
                            motestats['latencies'])
                        motestats['latency_avg_s'] = sum(
                            motestats['latencies'])/float(len(motestats['latencies']))
                        motestats['latency_max_s'] = max(
                            motestats['latencies'])
                        motestats['upstream_reliability'] = motestats['upstream_num_rx'] / \
                            float(motestats['upstream_num_tx'])
                        motestats['avg_hops'] = sum(
                            motestats['hops'])/float(len(motestats['hops']))
                    for (state, stats) in list(allstats[run_id][mote_id]['trickle'].items()):
                        motestats['trickle'][state] = stats

    # === network stats
    for (run_id, per_mote_stats) in list(allstats.items()):

        # -- define stats

        app_packets_sent = 0
        app_packets_received = 0
        app_packets_lost = 0
        joining_times = []
        us_latencies = []
        current_consumed = []
        lifetimes = []
        all_last_slotframe = {}

        trickle_stats = {}

        # -- compute stats

        for (mote_id, motestats) in list(per_mote_stats.items()):
            if mote_id == DAGROOT_ID:
                continue

            # counters

            app_packets_sent += motestats['upstream_num_tx']
            app_packets_received += motestats['upstream_num_rx']
            app_packets_lost += motestats['upstream_num_lost']

            # joining times

            if motestats['join_time_m'] is not None:
                joining_times.append(motestats['join_time_m'])

            # trickle timer

            for key in trickle_keys:
                val = [motestats['trickle'][x][key]
                       for x in motestats['trickle']]

                # populate
                if key not in trickle_stats:
                    trickle_stats[key] = []

                trickle_stats[key].extend(val)

            # mbr

            for key in last_slotframe_keys:
                if key in motestats:
                    val = motestats[key]
                    # populate
                    if key not in all_last_slotframe:
                        all_last_slotframe[key] = []
                    all_last_slotframe[key].append(val)

            # latency

            us_latencies += motestats['latencies']

            # current consumed
            mah = motestats['avg_current_uA'] / 3600
            current_consumed.append(mah)
            if motestats['lifetime_AA_years'] is not None:
                lifetimes.append(motestats['lifetime_AA_years'])
            current_consumed = [
                value for value in current_consumed if value is not None
            ]

        # -- save stats

        # temp_lifetimes = [i for i in lifetimes if type(i) is not str]

        allstats[run_id]['global-stats'] = {}

        val = current_consumed # 'unit': 'mAs / mC'
        new_key = "current-consumed"
        allstats[run_id]['global-stats'][new_key] = generate_stats(new_key, val)

        val = joining_times # 'unit': 'minutes'
        new_key = "joining-time"
        allstats[run_id]['global-stats'][new_key] = generate_stats(new_key, val)

        for key in trickle_keys:
            val = trickle_stats[key]
            new_key = "trickle_{}".format(key)
            stats = generate_stats(new_key, val)
            allstats[run_id]['global-stats'][new_key] = stats

        for key in all_last_slotframe.keys():
            val = all_last_slotframe[key]
            new_key = "last_{}".format(key)
            allstats[run_id]['global-stats'][new_key] = generate_stats(new_key, val)

    # === remove unnecessary stats
    remove_list = [
        'latencies',
        'sync_asn',
        'charge_asn',
        'charge',
        'join_asn',
        'upstream_pkts',
        'hops',
        'join_asn',
        'lifetime_AA_years',
        'sync_time_s',
        'upstream_num_lost',
        'upstream_num_rx',
        'upstream_num_tx'
    ]
    for (run_id, per_mote_stats) in list(allstats.items()):
        for (mote_id, motestats) in list(per_mote_stats.items()):

            for key in remove_list:
                if key in motestats:
                    del motestats[key]

            for key in all_last_slotframe.keys():
                if key in motestats:
                    del motestats[key]            

    return allstats

# =========================== main ============================================

def generate_stats(new_key, val, attach_value=False):
    val = [float(x) for x in val]
    stats = {
        'name': new_key,
        'sum': (
            sum(val)
            if val else 'N/A'
        ),
        'min': (
            min(val)
            if val else 'N/A'
        ),
        'max': (
            max(val)
            if val else 'N/A'
        ),
        'mean': (
            mean(val)
            if val else 'N/A'
        ),
        'median': (
            np.median(val)
            if val else 'N/A'
        ),
        '75%': (
            np.percentile(val, 75)
            if val else 'N/A'
        ),
        '95%': (
            np.percentile(val, 95)
            if val else 'N/A'
        ),
        'std': (
            np.std(val)
            if val else 'N/A'
        ),
        'var': (
            np.var(val)
            if val else 'N/A'
        ),
        'skew': (
            skew(val)
            if val else 'N/A'
        ),
        'kurtosis': (
            kurtosis(val)
            if val else 'N/A'
        ),
    }

    if attach_value: stats['values'] = val
    return [stats]


def generate_report(val):
    val = [float(x) for x in val]
    report = {
        'mean': (
            mean(val)
            if val else None
        ),
        'median': (
            np.median(val)
            if val else None
        ),
        'std': (
            np.std(val)
            if val else None
        ),
        'skew': (
            skew(val)
            if val else None
        ),
    }
    return report

def parseCliParams():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--method',
        dest='method',
        action='store',
        default='0',
        help='0: Create for folder that havent calculated kpi, 1: Replace all generated kpi',
    )
    parser.add_argument(
        '--compare',
        dest='compare',
        action='store',
        default='1',
        help='0: not doing comparison, 1: do comparison',
    )

    cliparams = parser.parse_args()
    return cliparams.__dict__


def main():
    cliparams = parseCliParams()

    # measured_metrics = {
    #     'trickle_pfree': 'mean',
    #     'joining-time': 'mean',
    #     'current-consumed': 'mean',
    # }

    measured_metrics = {
        'last_DIOtransmit': 'sum',
        'last_DIOsurpress': 'sum',
        'last_DIOtransmit_collision': 'sum',
    }

    subfolders = list(
        [os.path.join('simData', x) for x in os.listdir('simData')]
    )

    for subfolder in subfolders:
        if not os.path.isdir(subfolder):
            continue

        method_ = str(cliparams['method'])
        if method_ == "0":
            if len(glob.glob(os.path.join(subfolder, '*.dat.json'))) > 0:
                continue
        elif method_ == "1":
            pass

        for infile in glob.glob(os.path.join(subfolder, '*.dat')):
            print('\ngenerating KPIs for {0}'.format(infile))
        
            # gather the kpis
            kpis = kpis_all(infile)

            # # print on the terminal
            # print(json.dumps(kpis, indent=4))

            # add to the data folder
            outfile = '{0}.json'.format(infile)
            with open(outfile, 'w') as f:
                f.write(json.dumps(kpis, indent=4))
            print('KPIs saved in {0}'.format(outfile))
        
    compare_ = str(cliparams['compare'])

    if not compare_: return

    df_ = None
    for subfolder in subfolders:
        if not os.path.isdir(subfolder):
            continue
        
        mthd = subfolder.split('/')[1]
        for infile in glob.glob(os.path.join(subfolder, '*.dat.json')):
            with open(infile, 'r') as f:
                data = json.load(f)
                for run_id in data.keys():
                    result = {'method': mthd, 'run_id': run_id}
                    stats = data[run_id]['global-stats']
                    for key in measured_metrics.keys():
                        sub_key = measured_metrics[key]
                        value = stats[key][0][sub_key]
                        result[key] = value
                    
                    if df_ is None:
                        df_ = pd.DataFrame(columns=result.keys())
                    df_ = df_.append(result, ignore_index = True)
            break
    
    path_ = os.path.join('simData', 'comparison_all.csv')
    df_.sort_values(by='method', inplace=True, ignore_index=True)
    df_.to_csv(path_, index=False)

    path2 = os.path.join('simData', 'comparison_merged.csv')
    df2 = df_.copy()
    df2 = df2.drop(['run_id'], axis=1, errors='ignore')
    df2.loc[:, df2.columns != 'method'] = df2.loc[:, df2.columns != 'method'].astype('float')
    df2 = df2.groupby('method').aggregate([np.mean, np.std])

    df2.columns = df2.columns.map('-'.join)
    df2 = df2.reset_index()

    # temp
    values = df2['method'].values
    new_values = []
    sort_temp = []
    parameter = []
    for v in values:
        # ac_2_n10-i5
        m = v.split("_")[0]
        m = str(m).upper()

        n = v.split("_n")[1].split("-")[0]
        i = v.split("-i")[1]

        new_values.append(m)
        parameter.append(f"({n}, {i})")

        if m == 'ORI':
            id_ = 1
        elif m == 'RIATA':
            id_ = 2
        elif m == 'AC':
            id_ = 3
        else:
            id_ = 4

        sort_temp.append(f"{n}-{i}-{id_}")

    df2['method'] = new_values
    df2['parameter'] = parameter
    df2['sort_temp'] = sort_temp
    df2.sort_values(by='sort_temp', inplace=True, ignore_index=True)
    df2.drop(['sort_temp'], axis=1, errors='ignore', inplace=True)

    df2.to_csv(path2, index=False)


if __name__ == '__main__':
    main()
