from __future__ import division
from __future__ import print_function

# =========================== adjust path =====================================

import os
import sys
import argparse
from scipy.stats import skew, kurtosis
import pandas as pd
import netaddr
from multiprocessing import Process
import shutil

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

N_default = 5
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
        'sync_time_m': None,
        'rpljoin_asn': None,
        'rpljoin_time_m': None,
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
    all_joined = {}

    time_ms = ['t', 't_start', 't_end', 'interval', 'listen_period']

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

            if allstats[run_id][mote_id]['sync_time_m'] is not None:
                continue
            
            allstats[run_id][mote_id]['sync_asn'] = asn
            allstats[run_id][mote_id]['sync_time_m'] = asn * \
                file_settings['tsch_slotDuration'] / 60

        elif logline['_type'] == SimLog.LOG_SECJOIN_JOINED['type']:
            # joined

            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot join times
            if mote_id == DAGROOT_ID:
                continue

            if allstats[run_id][mote_id]['join_time_m'] is not None:
                continue

            # populate
            assert allstats[run_id][mote_id]['sync_asn'] is not None
            allstats[run_id][mote_id]['join_asn'] = asn
            allstats[run_id][mote_id]['join_time_m'] = asn * \
                file_settings['tsch_slotDuration'] / 60

        elif logline['_type'] == SimLog.LOG_MC_TR['type']:
            # only log non-dagRoot sync times
            if mote_id == DAGROOT_ID:
                continue

            if 'mc_tr' not in allstats[run_id][mote_id]:
                allstats[run_id][mote_id]['mc_tr'] = {}

            packet_type = logline['packet_type']
            if packet_type not in allstats[run_id][mote_id]['mc_tr']:
                allstats[run_id][mote_id]['mc_tr'][packet_type] = 0

            allstats[run_id][mote_id]['mc_tr'][packet_type] += 1

        elif logline['_type'] == SimLog.LOG_ALL_JOINED['type']:
            all_joined['all_joined'] = logline['result']

        elif logline['_type'] == SimLog.LOG_SIMULATOR_END['type']:
            all_joined['end_slotframe'] = logline['result']

        elif logline['_type'] == SimLog.LOG_PACKET_DROPPED['type']:
            # only log non-dagRoot sync times
            if mote_id == DAGROOT_ID:
                continue

            packet = logline['packet']

            try:
                if not packet[u'app'][u'is_trickle']:
                    packet = None
            except:
                packet = None

            if packet is None:
                continue

            if 'dio_drop' not in allstats[run_id][mote_id]:
                allstats[run_id][mote_id]['dio_drop'] = {}

            reason = logline['reason']
            if reason not in allstats[run_id][mote_id]['dio_drop']:
                allstats[run_id][mote_id]['dio_drop'][reason] = 0

            allstats[run_id][mote_id]['dio_drop'][reason] += 1

        elif logline['_type'] == SimLog.LOG_TRICKLE_RESET['type']:
            # only log non-dagRoot sync times
            if mote_id == DAGROOT_ID:
                continue

            if 'tr_rst' not in allstats[run_id][mote_id]:
                allstats[run_id][mote_id]['tr_rst'] = {}

            packet_type = logline['reset_type']
            if packet_type not in allstats[run_id][mote_id]['tr_rst']:
                allstats[run_id][mote_id]['tr_rst'][packet_type] = 0

            allstats[run_id][mote_id]['tr_rst'][packet_type] += 1

        elif logline['_type'] == SimLog.LOG_RPL_JOINED['type']:
            # joined

            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot join times
            if mote_id == DAGROOT_ID:
                continue

            if allstats[run_id][mote_id]['rpljoin_time_m'] is not None:
                continue

            # populate
            assert allstats[run_id][mote_id]['sync_asn'] is not None
            allstats[run_id][mote_id]['rpljoin_asn'] = asn
            allstats[run_id][mote_id]['rpljoin_time_m'] = asn * \
                file_settings['tsch_slotDuration'] / 60

            if 'rpljoin_dio_type' not in all_joined:
                all_joined['rpljoin_dio_type'] = {}
            
            if 'dio_type' in logline:
                k = logline['dio_type']
                if k not in all_joined['rpljoin_dio_type']:
                    all_joined['rpljoin_dio_type'][k] = 0

                all_joined['rpljoin_dio_type'][k] += 1

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

        elif logline['_type'] == SimLog.LOG_PER_SLOTFRAME['type']:
            # shorthands
            mote_id = logline['_mote_id']

            # only log non-dagRoot
            if mote_id == DAGROOT_ID:
                continue

            for key in logline['result'].keys():
                new_key = f'per_slotframe_{key}'
                if new_key not in allstats[run_id][mote_id]:
                    allstats[run_id][mote_id][new_key] = []

                allstats[run_id][mote_id][new_key].append(
                    logline['result'][key])

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
                if key in time_ms:
                    value /= 1000
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
                        motestats['lifetime_AA_years'] = None
                    else:
                        # motestats['charge'] in millicoulombs
                        # motestats['avg_current_uA'] in mAs (seconds)
                        # 1 mAh = 1 * 3600 seconds
                        # 1 hour = 3600 seconds
                        # 1 mAs = mC
                        time = float(
                            (motestats['charge_asn']-motestats['sync_asn']) * file_settings['tsch_slotDuration'])
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
        joining_times = {
            'syncjoin': [],
            'secjoin': [],
            'sync_sec_diff': [],
            'rpljoin': [],
            'sec_rpl_diff': []
        }
        us_latencies = []
        current_consumed = []
        lifetimes = []
        all_last_slotframe = {}

        trickle_stats = {}

        dio_drop = {}
        mc_tr = {}
        tr_rst = {}

        # -- compute stats

        for (mote_id, motestats) in list(per_mote_stats.items()):
            if mote_id == DAGROOT_ID:
                continue

            if 'mc_tr' in motestats:
                for key in motestats['mc_tr'].keys():
                    if key not in mc_tr:
                        mc_tr[key] = 0
                    mc_tr[key] += motestats['mc_tr'][key]

            if 'dio_drop' in motestats:
                for key in motestats['dio_drop'].keys():
                    if key not in dio_drop:
                        dio_drop[key] = 0
                    dio_drop[key] += motestats['dio_drop'][key]

            if 'tr_rst' in motestats:
                for key in motestats['tr_rst'].keys():
                    if key not in tr_rst:
                        tr_rst[key] = 0
                    tr_rst[key] += motestats['tr_rst'][key]

            # counters

            app_packets_sent += motestats['upstream_num_tx']
            app_packets_received += motestats['upstream_num_rx']
            app_packets_lost += motestats['upstream_num_lost']

            # joining times
            if motestats['sync_time_m'] is not None:
                joining_times['syncjoin'].append(motestats['sync_time_m'])
            if motestats['join_time_m'] is not None:
                joining_times['secjoin'].append(motestats['join_time_m'])
            if motestats['rpljoin_time_m'] is not None:
                joining_times['rpljoin'].append(motestats['rpljoin_time_m'])
            
            if motestats['sync_time_m'] is not None and motestats['join_time_m'] is not None:
                diff = motestats['join_time_m'] - motestats['sync_time_m']
                joining_times['sync_sec_diff'].append(diff)

            if motestats['join_time_m'] is not None and motestats['rpljoin_time_m'] is not None:
                diff = motestats['rpljoin_time_m'] - motestats['join_time_m']
                joining_times['sec_rpl_diff'].append(diff)

            # trickle timer

            for key in trickle_keys:
                val = []
                for x in motestats['trickle']:
                    if key in motestats['trickle'][x]:
                        val.append(motestats['trickle'][x][key])

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
            if motestats['avg_current_uA']:
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

        new_key = "global-stats-engine"
        allstats[run_id]['global-stats'][new_key] = all_joined

        val = 1 - app_packets_lost / app_packets_sent if app_packets_sent > 0 else None
        new_key = "e2e-pdr"
        allstats[run_id]['global-stats'][new_key] = val

        val = us_latencies
        new_key = "e2e-latency"
        allstats[run_id]['global-stats'][new_key] = generate_stats(
            new_key, val)

        val = current_consumed  # 'unit': 'mAs / mC'
        new_key = "current-consumed"
        allstats[run_id]['global-stats'][new_key] = generate_stats(
            new_key, val)

        for k in joining_times.keys():
            val = joining_times[k]  # 'unit': 'minutes'
            new_key = f"{k}_time_m"
            allstats[run_id]['global-stats'][new_key] = generate_stats(
                new_key, val)

        allstats[run_id]['global-stats']['global_dio_drop'] = dio_drop
        allstats[run_id]['global-stats']['global_mc_tr'] = mc_tr
        allstats[run_id]['global-stats']['global_tr_rst'] = tr_rst
        allstats[run_id]['global-stats']['per_slotframe_run'] = int(file_settings['exec_numSlotframesPerRun'] / 100)

        for key in trickle_keys:
            val = trickle_stats[key]
            if len(val) == 0: continue
            new_key = "trickle_{}".format(key)
            if '_class' in key:
                stats = {}
                for k2 in val:
                    if k2 not in stats:
                        stats[k2] = 0
                    stats[k2] += 1
            else:
                stats = generate_stats(new_key, val)
            allstats[run_id]['global-stats'][new_key] = stats

        for key in all_last_slotframe.keys():
            if key == 'ql_table':
                continue

            val = all_last_slotframe[key]
            new_key = "last_{}".format(key)
            allstats[run_id]['global-stats'][new_key] = generate_stats(
                new_key, val)

        allstats[run_id]['global-stats']['last_pfailed'] = (
            allstats[run_id]['global-stats']['last_failed_dio'][0]['sum'] / allstats[run_id]['global-stats']['last_count_dio'][0]['sum']
        )
        allstats[run_id]['global-stats']['last_psent'] = 1 - allstats[run_id]['global-stats']['last_pfailed']

    # === remove unnecessary stats
    remove_list = [
        'latencies',
        'charge_asn',
        'charge',
        'upstream_pkts',
        'hops',
        'sync_asn',
        'join_asn',
        'rpljoin_asn',
        'lifetime_AA_years',
        'upstream_num_lost',
        'upstream_num_rx',
        'upstream_num_tx'
    ]
    for (run_id, per_mote_stats) in list(allstats.items()):
        for (mote_id, motestats) in list(per_mote_stats.items()):

            for key in remove_list:
                if key in motestats:
                    del motestats[key]

            # for key in all_last_slotframe.keys():
            #     if key in motestats:
            #         if key == 'ql_table':
            #             continue
            #         del motestats[key]

    return allstats

# =========================== main ============================================


def generate_stats(new_key, val, attach_value=False):
    if isinstance(val[-1], list): return []
    val = [float(x) for x in val if x is not None]
    stats = {
        'name': new_key,
        'count': (
            len(val)
            if val else None
        ),
        'sum': (
            sum(val)
            if val else None
        ),
        'min': (
            min(val)
            if val else None
        ),
        'max': (
            max(val)
            if val else None
        ),
        'mean': (
            mean(val)
            if val else None
        ),
        'median': (
            np.median(val)
            if val else None
        ),
        '75%': (
            np.percentile(val, 75)
            if val else None
        ),
        '95%': (
            np.percentile(val, 95)
            if val else None
        ),
        'std': (
            np.std(val)
            if val else None
        ),
        'var': (
            np.var(val)
            if val else None
        ),
        'skew': (
            skew(val)
            if val else None
        ),
        'kurtosis': (
            kurtosis(val)
            if val else None
        ),
    }

    if attach_value:
        stats['values'] = val
    return [stats]


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
    parser.add_argument(
        '--path',
        dest='path',
        action='store',
        default='',
        help='additional path',
    )
    parser.add_argument(
        '--test',
        dest='test',
        action='store',
        default='',
        help='is_test',
    )
    parser.add_argument(
        '--worker',
        dest='worker',
        action='store',
        default='',
        help='num_worker',
    )

    cliparams = parser.parse_args()
    return cliparams.__dict__


def exp4_process(df_, measured_metrics, base_path):
    base_path = os.path.join(base_path, "exp4_metrics")

    c_ = df_.columns.to_list()
    c_.remove('parameter')
    c_.remove('method')

    df_t = df_.pivot(index='parameter', columns='method', values=c_)
    df_t = df_t.reset_index()
    df_t.columns = df_t.columns.map('-'.join)

    df_t['n'] = df_t['parameter-'].str.replace(
        "(", "").str.replace(")", "").str.split(", ").str[0].astype(int)
    df_t['i'] = df_t['parameter-'].str.replace(
        "(", "").str.replace(")", "").str.split(", ").str[1].astype(int)
    df_t.sort_values(by=['n', 'i'], inplace=True)

    for c in df_t.columns:
        method = c.split("-")[-1]
        if len(method) > 1:
            new_col_name = method + "-" + c.replace(f"-{method}", "")
            df_t.rename(columns={c: new_col_name}, inplace=True)

    target_ = list(measured_metrics.keys())

    print(base_path)
    remove_create_folder(base_path)

    for col in target_:
        temp_dic = {}
        for i in df_t.columns[df_t.columns.str.contains(col)]:
            if 'ORI' in i:
                id_ = 10
            elif 'RIATA' in i:
                id_ = 20
            elif 'AC' in i:
                id_ = 30
            else:
                id_ = 40
            if "-std" in i:
                id_ += 1
            temp_dic[i] = id_

        sorted_cols = list(
            dict(sorted(temp_dic.items(), key=lambda item: item[1])).keys())
        cols = ["parameter-"] + sorted_cols
        dftt = df_t[cols]

        sub_keys = measured_metrics[col]
        for sub_key in sub_keys:
            new_key = f'{col}-{sub_key}'
            path = os.path.join(base_path, f"{new_key}.xlsx")
            dftt.to_excel(path, index=False)

# def exp4_table(df_, base_path):
#     base_path = os.path.join(base_path, "exp4_metrics")

#     c_ = df_.columns.to_list()
#     c_.remove('parameter')
#     c_.remove('method')

#     df_t = df_.pivot(index='parameter', columns='method', values=c_)
#     df_t = df_t.reset_index()
#     df_t.columns = df_t.columns.map('-'.join)

#     df_t['n'] = df_t['parameter-'].str.replace(
#         "(", "").str.replace(")", "").str.split(", ").str[0].astype(int)
#     df_t['i'] = df_t['parameter-'].str.replace(
#         "(", "").str.replace(")", "").str.split(", ").str[1].astype(int)
#     df_t.sort_values(by=['n', 'i'], inplace=True)

#     for c in df_t.columns:
#         method = c.split("-")[-1]
#         if len(method) > 1:
#             new_col_name = method + "-" + c.replace(f"-{method}", "")
#             df_t.rename(columns={c: new_col_name}, inplace=True)

#     target_ = [
#         'last_count_dio-sum-mean',
#         'last_failed_dio-sum-mean',
#         'last_trickle_surpress-sum-mean'
#     ]

#     print(base_path)
#     remove_create_folder(base_path)

#     df_t = df_t[df_t.columns[~df_t.columns.str.contains('-std')]]

#     temp_dic = {}
#     for i in df_t.columns[df_t.columns.str.contains(col)]:
#         if 'ORI' in i:
#             id_ = 10
#         elif 'RIATA' in i:
#             id_ = 20
#         elif 'AC' in i:
#             id_ = 30
#         else:
#             id_ = 40
#         temp_dic[i] = id_

#     sorted_cols = list(
#         dict(sorted(temp_dic.items(), key=lambda item: item[1])).keys())
#     cols = ["parameter-"] + sorted_cols
#     dftt = df_t[cols]

#     path = os.path.join(base_path, "tabel_dio.xlsx")
#     dftt.to_excel(path, index=False)

def generate_summary(infile):
    print('generating KPIs for {0}'.format(infile))

    # gather the kpis
    kpis = kpis_all(infile)

    # add to the data folder
    outfile = '{0}.json'.format(infile)
    with open(outfile, 'w') as f:
        f.write(json.dumps(kpis, indent=4))
    print('KPIs saved in {0}'.format(outfile))

def remove_create_folder(path):
    try:
        shutil.rmtree(path)
    except OSError:
        pass

    try:
        os.makedirs(path)
    except OSError:
        pass

def get_idval_text(lst, text):
    for i, x in enumerate(lst):
        if text in x:
            return i, x.replace(text, '')
    return None, None

def main():
    cliparams = parseCliParams()

    with open('measured_metrics.json', 'r') as f:
        measured_metrics = json.load(f)

    base_path = 'simData'
    add_path = str(cliparams['path'])
    if add_path:
        base_path += f'/{add_path}'

    subfolders = list(
        [os.path.join(base_path, x) for x in os.listdir(base_path)]
    )

    raw_files = []
    for subfolder in subfolders:
        if not os.path.isdir(subfolder) and 'exp' not in subfolder:
            continue

        method_ = str(cliparams['method'])
        if method_ == "0":
            if len(glob.glob(os.path.join(subfolder, '*.dat.json'))) > 0:
                continue
        elif method_ == "1":
            pass

        for infile in glob.glob(os.path.join(subfolder, '*.dat')):
            raw_files.append(infile)

    N = int(cliparams['worker'] or N_default)
    subList = [raw_files[n : n + N] for n in range(0, len(raw_files), N)]
    for sl in subList:
        processes = []

        for file in sl:
            proc = Process(target=generate_summary, args=(file,))
            processes.append(proc)

        for p in processes:
            p.start()

        for p in processes:
            p.join()

    compare_ = int(cliparams['compare'])

    if not compare_:
        return

    num_runs = None
    num_nodes = None
    df_ = None
    for subfolder in subfolders:
        if not os.path.isdir(subfolder) and 'exp' not in subfolder:
            continue

        mthd = subfolder.split('/')[-1]
        for infile in glob.glob(os.path.join(subfolder, '*.dat.json')):
            with open(infile, 'r') as f:
                data = json.load(f)
                num_runs = len(data.keys())
                for run_id in data.keys():
                    result = {'method': mthd, 'run_id': run_id}

                    num_nodes = 0
                    for mote_id in data[run_id].keys():
                        if mote_id == 'global-stats':
                            continue
                        jd = data[run_id][mote_id]['rpljoin_time_m']
                        if jd:
                            num_nodes += 1

                    stats = data[run_id]['global-stats']
                    for key in measured_metrics.keys():
                        sub_keys = measured_metrics[key]
                        for sub_key in sub_keys:
                            new_key = f'{key}-{sub_key}'
                            if sub_key == '':
                                value = stats[key]
                            else:
                                value = stats[key][0][sub_key]
                            result[new_key] = value

                    result['dead_nodes'] = len(
                        data[run_id].keys()) - 1 - num_nodes
                    result['alive_nodes'] = num_nodes

                    if df_ is None:
                        df_ = pd.DataFrame(columns=result.keys())
                    df_ = df_.append(result, ignore_index=True)

    if not df_.empty:
        path_ = os.path.join(base_path, 'comparison_all.csv')
        path2 = os.path.join(base_path, 'comparison_merged.csv')
        exp = ''

        df_.sort_values(by='method', inplace=True, ignore_index=True)
        df_.to_csv(path_, index=False, sep ='\t')
        
        df2 = df_.copy()
        df2 = df2.drop(['run_id'], axis=1, errors='ignore')
        df2.loc[:, df2.columns != 'method'] = df2.loc[:,
                                                      df2.columns != 'method'].astype('float')

        base_func = [np.mean]
        funcs = base_func if num_runs == 1 else base_func + [np.std]

        df2 = df2.groupby('method').aggregate(funcs)
        df2.columns = df2.columns.map('-'.join)
        df2 = df2.reset_index()
        # df2 = df2.fillna(0)

        is_test = bool(cliparams.get('test', 0))

        if not is_test:
            methods = df2['method'].values
            df2['ori_name'] = df2['method'].values
            if df2['method'].str.contains('exp1').sum():
                new_values = []
                for a in methods:
                    param = a.split('_')
                    _, dr = get_idval_text(param, 'dr')
                    name = f'{dr}'
                    new_values.append(name)
                df2['method'] = new_values
                df2.sort_values(by='method', inplace=True, ignore_index=True)
                exp = 1

            elif df2['method'].str.contains('exp2').sum():
                new_values = []
                for a in methods:
                    param = a.split('_')
                    _, lr = get_idval_text(param, 'lr')
                    name = f'{lr}'
                    new_values.append(name)
                df2['method'] = new_values
                df2.sort_values(by='method', inplace=True, ignore_index=True)
                exp = 2

            elif df2['method'].str.contains('exp3').sum():
                new_values = []
                for a in methods:
                    param = a.split('_')
                    _, ep = get_idval_text(param, 'ep')
                    name = f'{ep}'
                    new_values.append(name)
                df2['method'] = new_values
                df2.sort_values(by='method', inplace=True, ignore_index=True)
                exp = 3


            elif df2['method'].str.contains('exp4').sum():
                new_values = []
                sort_temp = []
                parameter = []
                for v in methods:
                    param = v.split('_')
                    _, i = get_idval_text(param, 'imin')
                    _, n = get_idval_text(param, 'motes')

                    m = str(param[0]).upper()
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

                exp4_process(df2, measured_metrics, base_path)
                # exp4_table(df2, base_path)
                exp = 4

        df2.to_csv(path2, index=False, sep ='\t')
        path2_ = os.path.join(base_path, f'comparison_merged_exp{exp}.xlsx')
        df2.to_excel(path2_, index=False)


if __name__ == '__main__':
    main()
