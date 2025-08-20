#!/usr/bin/env python3
'''
Created on May 14, 2025

@author: jhancock

Script(s) to load, merge, validate YAML files for FastEddy for CIT purposes.

'''

import logging
import os
import socket
import yaml
from datetime import datetime

# Some useful "constants"
ACCOUNT = 'account'
BATCHSTEPS = 'batchsteps'
CASPER = 'casper'
COMMAND = 'command'
COMPILE = 'compile'
DEFAULT_YML = 'tests/config/default.yml'
DERECHO = 'derecho'
DEVELOP = 'develop'
DOE_OLCF = 'deo_olcf'
ECONOMY = 'economy'
ENABLED = 'enabled'
ENVIRONMENT = 'environment'
ENVIRONMENTS_PATH = 'tests/config/environments'
EXAMPLES = 'examples'
EXECUTION = 'execution'
FRONTIER = 'frontier'
HOSTNAME = 'hostname'
IN_FILE_EXT = '.in'
JOB_NAME = 'job_name'
JOIN_OUTPUT = 'join_output'
LAUNCHER = 'launcher'
MACHINE = 'machine'
MAIN = 'main'
MPIEXEC = 'mpiexec'
MPIRUN = 'mpirun'
MPI_RANKS = 'mpi_ranks'
NSF_NCAR = 'nsf_ncar'
OUTPUT_DIR = 'output_dir'
OUTPUTFREQ = 'outputfreq'
PATHS = 'paths'
PBS = 'pbs'
PREEMPT = 'preempt'
PREMIUM = 'premium'
PRIORITY = 'priority'
PYTEST_REF_DIR = 'pytest_ref_dir'
PYTEST_REPORT_NAME = 'pytest_report_name'
QUEUE = 'queue'
REGULAR = 'regular'
REPO_ROOT = 'repo_root'
SET_GPU_RANK = 'set_gpu_rank'
SCHEDULER = 'scheduler'
SLURM = 'slurm'
SUMMIT = 'summit'
TEST_CASES = 'test_cases'
TEST_SUITES_PATH = 'tests/test_suites'
TIMESTEPS = 'timesteps'
TUTORIALS = 'tutorials'
WALLTIME = 'walltime'
YML_EXT = '.yml'

# Lists of valid values for particular keys
VALID_COMMANDS = [MPIRUN, MPIEXEC]
VALID_ENVIRONMENTS = [NSF_NCAR, DOE_OLCF]
VALID_LAUNCHERS = [SET_GPU_RANK]
VALID_PRIORITIES = [REGULAR, PREMIUM, ECONOMY]
VALID_QUEUES = [CASPER, DERECHO, MAIN, PREEMPT, DEVELOP]

def load_and_merge_config(config_fn, suite, logger=None): 
    """Load and merge the configuration files for the suite of tests.
    
    Load the appropriate configuration files, which each subsequent one over-riding the previous one(s), in this order:
    1. default.yml
    2. pbs.yml (unless config_file specifies a different scheduler, then maybe slurm.yml (future)
    3. casper.yml or derecho.yml, determined by hostname (or possibly summit.yml or frontier.yml (future))
    4. If supplied, the specified test suite (minimal or comprehensive)
    5. config_file
    
    Returns a dictionary of configuration values
    """
    
    # Load the specified config file.  Even though this comes last in the merge, we need a few things from it 
    # to start with, such as the repo_location
    with open(config_fn) as config_file:
        specified_config = yaml.load(config_file, Loader=yaml.SafeLoader)
    
    logger.info('specified_config: ' + str(specified_config))
    
    try:
        repo_root = specified_config[PATHS][REPO_ROOT]
    except KeyError:
        logger.info('Required configuration key not found: ' + PATHS + '.' + REPO_ROOT)
        exit(1)
    logger.info(REPO_ROOT + ': ' + str(repo_root))
    
    # Check that the repo_root exists before using it
    if not os.path.isdir(repo_root):
        logger.info(REPO_ROOT + ' ' + ' does not exist.  Stopping.')
        exit(1)
    
    # 1. Now load the default.yml, now that we know where to find it
    default_config_path = os.path.join(repo_root, DEFAULT_YML)
    with open(default_config_path) as default_config_file:
        default_config = yaml.load(default_config_file, Loader=yaml.SafeLoader)
    
    logger.info('default_config: ' + str(default_config))
    
    # Merge the specified config onto the default.  Even though it will be merged again at the end, we want to handle
    # the possible over-rides of environment and/or scheduler
    merged_config = merge_configs(default_config, specified_config)
    logger.info('(preliminary) merged_config: ' + str(merged_config))
    
    try:
        environment = merged_config[ENVIRONMENT]
    except KeyError:
        logger.info('Required configuration key not found: ' + ENVIRONMENT)
        exit(2)
    logger.info(ENVIRONMENT + ': ' + str(environment))
    
    try:
        scheduler = merged_config[SCHEDULER]
    except KeyError:
        logger.info('Required configuration key not found: ' + SCHEDULER)
        exit(3)
    logger.info(SCHEDULER + ': ' + str(scheduler))
    
    # 2. Load and merge the scheduler config
    if len(scheduler) < 4 or scheduler[-4] != YML_EXT:
        scheduler += YML_EXT
    scheduler_config_path = os.path.join(repo_root, ENVIRONMENTS_PATH, environment, SCHEDULER, scheduler)
    logger.info('scheduler_config_path: ' + scheduler_config_path)
    with open(scheduler_config_path) as scheduler_config_file:
        scheduler_config = yaml.load(scheduler_config_file, Loader=yaml.SafeLoader)
        
    logger.info('scheduler_config: ' + str(scheduler_config))
    
    # Merge default and scheduler configs
    merged_config = merge_configs(default_config, scheduler_config)
    logger.info('merged_config: ' + str(merged_config))
    
    # 3. Get the hostname  and load and merge the machine config
    hostname = socket.gethostname()
    logger.info(HOSTNAME + ': ' + hostname)
    if len(hostname) >= 7 and hostname[:7] == DERECHO:
        host = DERECHO
    elif len(hostname) >= 6 and hostname[:6] == CASPER:
        host = CASPER
    elif len(hostname) >= 6 and hostname[:6] == SUMMIT:
        host = SUMMIT
    elif len(hostname) >= 8 and hostname[:8] == FRONTIER:
        host = FRONTIER
    else: # Default to enable some initial testing on other machines such as eldorado
        host = DERECHO
    
    logger.info('host: ' + host)
    host_yml = host + YML_EXT
    
    # Merge in the machine config
    machine_config_path = os.path.join(repo_root, ENVIRONMENTS_PATH, environment, MACHINE, host_yml)
    with open(machine_config_path) as machine_config_file:
        machine_config = yaml.load(machine_config_file, Loader=yaml.SafeLoader)
        
    logger.info('machine_config ' + str(machine_config))
    
    # Merge machine config into merged config
    merged_config = merge_configs(merged_config, machine_config)
    logger.info('merged_config ' + str(merged_config))
    
    # 4. Load the suite, if specified
    logger.info('suite: ' + suite)
    
    # Is there always going to be one?  I'm thinking it should be optional, but TBD, needs discussion.
    if len(suite) > 0:
        suite_yml = suite + YML_EXT
        suite_config_path = machine_config_path = os.path.join(repo_root, TEST_SUITES_PATH, suite_yml)
        with open(suite_config_path) as suite_config_file:
            suite_config = yaml.load(suite_config_file, Loader=yaml.SafeLoader)
        
        # Merge suite config into merged config
        merged_config = merge_configs(merged_config, suite_config)
        logger.info('merged_config (with suite): ' + str(merged_config))
        
    # 5. Merge the specified config into the merged config
    merged_config = merge_configs(merged_config, specified_config)
    logger.info('merged_config (after final merge of the specified config): ' + str(merged_config))
    
    # 6. Expand any environment variables in any of the paths
    for path in merged_config[PATHS].keys():
        merged_config[PATHS][path] = os.path.expandvars(merged_config[PATHS][path])
    
    logger.info('merged_config after expanding environment variables in paths: ' + str(merged_config))
    
    # 7. The following may be specified at the top level, and also within each test case:
    #    timesteps
    #    outputfreq
    #    batchstps
    #   
    #    Roll this up into each test case, then delete the ones at the top level, so that the rest of the code only needs
    #    to look for them in one place (in each test case).  If specified at the test case level, that over-rides the 
    #    more general value at the top level, so only copy the top level value into a test case if it doesn't have that
    #    key already.
    for key in [TIMESTEPS, OUTPUTFREQ, BATCHSTEPS]:
        if key in merged_config:
            for test_case in merged_config[TEST_CASES]:
                for test_case_name in test_case.keys(): # There will be only one key for the test case, which is its name
                    test_case_config = test_case[test_case_name]
                    # See if 
                    if not key in test_case_config:
                        # Add the top level value to the config of the test case
                        test_case_config[key] = merged_config[key]
            # Now remove the top level key/value pair
            del merged_config[key]
    
    logger.info('merged_config after rolling up steps values to test cases: ' + str(merged_config))
    
    return merged_config
    
    
def merge_configs(base, override):
    for key in override:
        if key in base:
            if isinstance(base[key], dict) and isinstance(override[key], dict):
                merge_configs(base[key], override[key])
            elif base[key] != override[key]:
                # Over-ride the base value
                base[key] = override[key]
        else:
            # Add the new key/value pair to the base dictionary
            base[key] = override[key]
    return base


def validate_cfg(config, required_keys, logger=None):
    """Validate the configuration file, making sure it contains the required keys
    
    required_keys is a list of keys, each potentially being nested and separated by periods.  Example: paths.repo_root
    """
    
    logger.info('Validating configuration.')
    
    # Iterate over the "compound" keys
    for compound_key in required_keys:
        logger.info('Required key: ' + compound_key)
        # Get a list of the keys separated by periods
        keys = compound_key.split('.')
        # Initialize value to the whole dictionary
        value = config
        for key in keys:
            # See if the key is in the current level of dictionary
            if key in value:
                # Get the value of the key, which may be another dictionary
                value = value[key] 
            else:
                logger.info('Required key not found: ' + compound_key)
                exit(4)
        logger.info('Value of ' + compound_key + str(value))
    
    # Check that there is at lease one test case
    try:
        test_cases = config[TEST_CASES]
    except KeyError:
        logger.info('Required configuration key not found: ' + TEST_CASES)
        exit(5)
    num_test_cases = len(test_cases)
    if num_test_cases < 1:
        logger.info('No test cases specified. Stopping.')
        exit(5)
    else:
        logger.info(str(num_test_cases) + ' test cases specified.')
        
    #  Check test_case settings
    paths = config[PATHS]
    repo_root = paths[REPO_ROOT]
    examples_path = os.path.join(repo_root, TUTORIALS, EXAMPLES)
    any_missing = False
    for test_case in test_cases:
        for key in test_case.keys(): # There will be only one key for the test case, which is its name
            #  Check that there is a .in file for the test in tutorials/examples in the repo.
            filepath = os.path.join(examples_path, key + IN_FILE_EXT) 
            if not os.path.exists(filepath):
                logger.info('Necessary file missing: ' + filepath + '. Stopping.')
                exit(6)
            
            # Make sure the pytest_ref_dir exists
            test_case_settings = test_case[key]
            ref_dir = test_case_settings[PYTEST_REF_DIR]
            if not os.path.isdir(ref_dir):
                logger.info('Pytest reference dir ' + ref_dir + ' does not exist. Stopping')
                exit(7)
            
            # Make sure the pytest_report_name is a str
            report_name = test_case_settings[PYTEST_REPORT_NAME]
            if not type(report_name) == str:
                logger.info('Value of ' + TEST_CASES + '.' + key + '.' + PYTEST_REPORT_NAME + ' is not a string type: ' + account)
                exit(8)
                
            #   timesteps - make sure it's an int
            try:
                timesteps = test_case_settings[TIMESTEPS]
                if not type(timesteps) == int:
                    logger.info('Value of ' + TEST_CASES + '.' + key + '.' + TIMESTEPS + ' is not an int type: ' + timesteps)
                    exit(9)
            except KeyError:
                pass # Not required
        
            #   outputfreq - make sure it's an int
            try:
                outputfreq = test_case_settings[OUTPUTFREQ]
                if not type(outputfreq) == int:
                    logger.info('Value of ' + TEST_CASES + '.' + key + '.' + OUTPUTFREQ + ' is not an int type: ' + outputfreq)
                    exit(10)
            except KeyError:
                pass # Not required
        
            #   batchsteps - make sure it's an int
            try:
                batchsteps = test_case_settings[BATCHSTEPS]
                if not type(batchsteps) == int:
                    logger.info('Value of ' + TEST_CASES + '.' + key + '.' + BATCHSTEPS + ' is not an int type: ' + batchsteps)
                    exit(11)
            except KeyError:
                pass # Not required
    
    # Already checked that repo_root is a directory in load_and_merge_config.
    
    # Check that the output_dir exists or can be created
    date_str = datetime.now().strftime("%Y%m%d")  # e.g. 20250812
    output_dir = str(paths[OUTPUT_DIR]) + "_" + date_str
    if not os.path.isdir(output_dir):
        logger.info('Output dir ' + output_dir + ' does not exist.  Will try to create it.')
        # Doesn't exist (yet), but can we create it?
        try:
            os.makedirs(output_dir)
        except Exception as e:
            logger.info('Could not create output directory.  Stopping. ' + str(e))
            exit(12)
    
    #   compile_enabled - check that it's a bool
    compile_enabled = config[COMPILE][ENABLED]
    if not type(compile_enabled) == bool:
        logger.info('Value of ' + COMPILE + '.' + ENABLED + ' is not a bool type (true or false): ' + compile_enabled)
        exit(13)
            
    # Check execution values.
    #    mpi_ranks - make sure it's an int
    mpi_ranks = config[EXECUTION][MPI_RANKS]
    if not type(mpi_ranks) == int:
        logger.info('Value of ' + EXECUTION + '.' + MPI_RANKS + ' is not an int type: ' + mpi_ranks)
        exit(14)
            
    #    launcher - check against list of valid values
    launcher = config[EXECUTION][LAUNCHER]
    if not launcher in VALID_LAUNCHERS:
        logger.info('Invalid value of ' + EXECUTION + '.' + LAUNCHER + ': ' + launcher)
        exit(15)
        
    # Check scheduler settings - depends on what schedulre is specified (only pbs is supported so far)
    scheduler = config[SCHEDULER]
    
    if scheduler == PBS:
        #    pbs
        #       account - check that it's a string
        account = config[EXECUTION][PBS][ACCOUNT]
        if not type(account) == str:
            logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + ACCOUNT + ' is not a string type: ' + account)
            exit(16)
            
        #       job_name - check that it's a string
        job_name = config[EXECUTION][PBS][JOB_NAME]
        if not type(job_name) == str:
            logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + JOB_NAME + ' is not a string type: ' + job_name)
            exit(17)
            
        #       walltime - check that it's a string, with 3 integers separated by colons, each in proper range
        walltime = config[EXECUTION][PBS][WALLTIME]
        if not type(job_name) == str:
            logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + WALLTIME + ' is not a string type: ' + walltime)
            exit(18)
        else:
            # Check some more things...
            components = walltime.split(':')
            if len(components) != 3:
                logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + WALLTIME + ' does not appear to be in the correct format of "HH:MM:SS": ' + walltime)
                exit(19)
            else:
                # Check that the components look like ints
                for i in range(len(components)):
                    comp = components[i]
                    try:
                        comp_val = int(comp)
                        if (i != 0) and (comp_val > 59 or comp_val < 0):
                            logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + WALLTIME + ' does not appear to be in the correct format of "HH:MM:SS": ' + walltime + '. (MM or SS is not between 0 and 59)')
                            exit(19)
                    except:
                        logger.info('Value of ' + EXECUTION + '.' + PBS + '.' + WALLTIME + ' does not appear to be in the correct format of "HH:MM:SS": ' + walltime)
                        exit(19)
        
        #       queue - check against list of valid values
        queue = config[EXECUTION][PBS][QUEUE]
        if not queue in VALID_QUEUES:
            logger.info('Invalid value of ' + EXECUTION + '.' + PBS + ': ' + QUEUE)
            exit(20)
        
        #       join_output - check that it's a bool
        join_output = config[EXECUTION][PBS][JOIN_OUTPUT]
        if not type(join_output) == bool:
            logger.info('Value of ' + EXECUTION + '.' + PBS  + '.' + JOIN_OUTPUT + ' is not a bool type (true or false): ' + join_output)
            exit(21)
        
        #       priority - check against list of valid values
        priority = config[EXECUTION][PBS][PRIORITY]
        if not priority in VALID_PRIORITIES:
            logger.info('Invalid value of ' + EXECUTION + '.' + PBS  + '.' + PRIORITY + ': ' + priority)
            exit(22)
        
        #       command - check against list of valid values
        command = config[EXECUTION][PBS][COMMAND]
        if not command in VALID_COMMANDS:
            logger.info('Invalid value of ' + EXECUTION + '.' + PBS  + '.' + COMMAND + ': ' + command)
            exit(23)
        
    elif scheduler == SLURM:
        logger.info(SLURM + 'scheduler not yet implemented. Stopping.')
        exit(24)
    else:
        logger.info('Unsupported scheduler: ' + scheduler + '. Stopping.')
        exit(25)
        
    #   environment - check against list of valid values
    environment = config[ENVIRONMENT]
    if not environment in VALID_ENVIRONMENTS:
        logger.info('Invalid value of ' + ENVIRONMENT + ': ' + environment)
        exit(26)
    elif environment == DOE_OLCF:
        logger.info(DOE_OLCF + 'environment not yet implemented. Stopping.')
        exit(26)
        
    logger.info('Configuration is OK.')
        
