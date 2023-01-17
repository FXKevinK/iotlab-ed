#!/usr/bin/python
"""
\brief Holds the overall configuration of a simulation.

Configuration is read from a configuration file, and accessible in dotted
notation:

   simconfig.execution.numCores

This configuration contains the different steps of a simulation, including
what gets called after the simulation is done.
A single configuration turns into multiple SimSettings, for each combination
of settings.

\author Thomas Watteyne <thomas.watteyne@inria.fr>
"""
from __future__ import absolute_import

# =========================== imports =========================================

from builtins import str
import json
import glob
import os
import platform
import sys
import time

from . import SimSettings

# =========================== defines =========================================

# =========================== body ============================================

class DotableDict(dict):

    __getattr__= dict.__getitem__

    def __init__(self, d):
        self.update(**dict((k, self.parse(v))
                           for k, v in d.items()))

    @classmethod
    def parse(cls, v):
        if isinstance(v, dict):
            return cls(v)
        elif isinstance(v, list):
            return [cls.parse(i) for i in v]
        else:
            return v

class SimConfig(dict):

    # class variables, which are shared among all the instances
    _startTime          = None
    _log_directory_name = None

    def __init__(self, configfile=None, configdata=None, changed_param=None):

        if SimConfig._startTime is None:
            # startTime needs to be initialized
            SimConfig._startTime = time.time()

        if configfile is not None:
            # store params
            self.configfile = configfile

            # read config file
            if configfile == u'-':
                # read config.json from stdin
                self._raw_data = sys.stdin.read()
            else:
                with open(self.configfile, u'r') as file:
                    self._raw_data = file.read()
        elif configdata is not None:
            self._raw_data = configdata
        else:
            raise Exception()

        self.config_temp = json.loads(self._raw_data)
        if changed_param is not None and isinstance(changed_param, dict):
            check_regular_param = {
                'exec_randomSeed': str,
                'dio_interval_min_s': int,
                'ql_learning_rate': float,
                'ql_discount_rate': float,
                'ql_epsilon': float,
                'ql_adaptive_epsilon': bool,
                'ql_adaptive_decay_rate': float,
            }
            
            for key, func in check_regular_param.items():
                if key in changed_param:
                    val = func(changed_param[key])
                    self.config_temp['settings']['regular'][key] = val

            key = 'numRuns'
            if key in changed_param:
                val = int(changed_param[key])
                self.config_temp['execution'][key] = val

            key = 'exec_numMotes'
            if key in changed_param:
                val = int(changed_param[key])
                self.config_temp['settings']['combination'][key] = [val]

            key = 'log_directory_name'
            if key in changed_param:
                val = "trickle {}".format(changed_param[key])
                self.config_temp[key] = val
        
        self._raw_data = json.dumps(self.config_temp)

        # store config
        self.config   = DotableDict(self.config_temp)

        # decide a directory name for log files
        if SimConfig._log_directory_name is None:
            self._decide_log_directory_name()

    def __getattr__(self, name):
        return getattr(self.config, name)

    def get_config_data(self):
        return self._raw_data

    def get_log_directory_name(self):
        return SimConfig._log_directory_name

    @classmethod
    def get_startTime(cls):
        return cls._startTime

    @staticmethod
    def generate_config(settings_dict, random_seed):
        regular_field = settings_dict
        # remove cpuID, run_id, log_directory, and combinationKeys, which
        # shouldn't be in the regular field
        del regular_field[u'cpuID']
        del regular_field[u'run_id']
        del regular_field[u'logRootDirectoryPath']
        del regular_field[u'logDirectory']
        del regular_field[u'combinationKeys']
        # put random seed
        regular_field[u'exec_randomSeed'] = random_seed

        # save exec_numMotes value and remove 'exec_numMotes' from
        # regular_field
        exec_numMote = regular_field[u'exec_numMotes']
        del regular_field[u'exec_numMotes']

        config_json = {
            'settings': {
                'combination': {'exec_numMotes': [exec_numMote]},
                'regular': regular_field
            }
        }
        config_json[u'version'] = 0
        config_json[u'post'] = []
        config_json[u'log_directory_name'] = u'startTime'
        config_json[u'logging'] = u'all'
        config_json[u'execution'] = {
            u'numCPUs': 1,
            u'numRuns': 1
        }
        return config_json

    def _decide_log_directory_name(self):

        assert SimConfig._log_directory_name is None

        if "trickle" in self.log_directory_name:
            method = self.config['settings']['regular']['trickle_method']
            subfolders = list(
                [os.path.join(SimSettings.SimSettings.DEFAULT_LOG_ROOT_DIR, x) for x in os.listdir(SimSettings.SimSettings.DEFAULT_LOG_ROOT_DIR) if method in x]
            )
            index = len(subfolders) + 1
            log_directory_name = u'_'.join((method, str(index)))
            exp_ = str(self.log_directory_name).split(" ")[-1]

            log_directory_name += '_exp{}'.format(exp_)

            if "1" == exp_:
                ql_learning_rate = self.config['settings']['regular']['ql_learning_rate']
                ql_discount_rate = self.config['settings']['regular']['ql_discount_rate']
                ql_epsilon = self.config['settings']['regular']['ql_epsilon']
                log_directory_name = u'{}_lr{}-dr{}-ep{}'.format(log_directory_name, ql_learning_rate, ql_discount_rate, ql_epsilon)
            elif "2" == exp_:
                use_adaptive = self.config['settings']['regular']['ql_adaptive_epsilon']
                adaptive_epsilon = "adaptive" if use_adaptive else "static"
                ql_learning_rate = self.config['settings']['regular']['ql_learning_rate']
                ql_discount_rate = self.config['settings']['regular']['ql_discount_rate']
                epsilon_var = self.config['settings']['regular']['ql_adaptive_decay_rate'] if use_adaptive else self.config['settings']['regular']['ql_epsilon']
                log_directory_name = u'{}_lr{}-dr{}-{}{}'.format(log_directory_name, ql_learning_rate, ql_discount_rate, adaptive_epsilon, epsilon_var)
            elif "3" == exp_:
                num_motes = self.config['settings']['combination']['exec_numMotes'][0]
                imin = self.config['settings']['regular']['dio_interval_min_s']
                log_directory_name = u'{}_n{}-i{}'.format(log_directory_name, num_motes, imin)
            elif "eb" == exp_:
                ei = self.config['settings']['regular']['eb_interval_s']
                log_directory_name = u'{}_ei{}'.format(log_directory_name, ei)

        elif self.log_directory_name == u'startTime':
            # determine log_directory_name
            log_directory_name = u'{0}-{1:03d}'.format(
                time.strftime(
                    "%Y%m%d-%H%M%S",
                    time.localtime(int(SimConfig._startTime))
                ),
                int(round(SimConfig._startTime * 1000)) % 1000
            )
        elif self.log_directory_name == u'hostname':
            # hostname is stored in platform.uname()[1]
            hostname = platform.uname()[1]
            log_directory_path = os.path.join(
                SimSettings.SimSettings.DEFAULT_LOG_ROOT_DIR,
                hostname
            )
            # add suffix if there is a directory having the same hostname
            if os.path.exists(log_directory_path):
                index = len(glob.glob(log_directory_path + u'*'))
                log_directory_name = u'_'.join((hostname, str(index)))
            else:
                log_directory_name = hostname
        else:
            raise NotImplementedError(
                u'log_directory_name "{0}" is not supported'.format(
                    self.log_directory_name
                )
            )

        SimConfig._log_directory_name = log_directory_name
