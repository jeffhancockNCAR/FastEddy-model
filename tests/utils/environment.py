#!/usr/bin/env python3
'''
Created on May 14, 2025

@author: jhancock

Script(s) to load, merge, validate YAML files for FastEddy for CIT purposes.

'''
import os
import socket
import yaml

known_hosts = ['derecho']

def load_and_merge_config(config_fn, suite): 
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
    
    print('specified_config:', specified_config)
    
    repo_root = specified_config['paths']['repo_root']
    print('repo_root:', repo_root)
    
    # 1. Now load the default.yml, now that we know where to find it
    default_config_path = os.path.join(repo_root, 'tests/config/default.yml')
    with open(default_config_path) as default_config_file:
        default_config = yaml.load(default_config_file, Loader=yaml.SafeLoader)
    
    print('default_config:', default_config)
    
    # Merge the specified config onto the default.  Even though it will be merged again at the end, we want to handle
    # the possible over-rides of environment and/or scheduler
    merged_config = merge_configs(default_config, specified_config)
    
    print('(prelminary) merged_config:', merged_config)
    
    environment = merged_config['environment']
    scheduler = merged_config['scheduler']
    
    print('environment:', environment)
    print('scheduler:', scheduler)
    
    # 2. Load and merge the scheduler config
    if len(scheduler) < 4 or scheduler[-4] != '.yml':
        scheduler += '.yml'
    scheduler_config_path = os.path.join(repo_root, 'tests/config/environments', environment, 'scheduler', scheduler)
    print('scheduler_config_path:', scheduler_config_path)
    with open(scheduler_config_path) as scheduler_config_file:
        scheduler_config = yaml.load(scheduler_config_file, Loader=yaml.SafeLoader)
        
    print('scheduler_config:', scheduler_config)
    
    # Merge default and scheduler configs
    merged_config = merge_configs(default_config, scheduler_config)
    print('merged_config:', merged_config)
    
    # 3. Get the hostname  and load and merge the machine config
    hostname = socket.gethostname()
    print('hostname:', hostname)
    if len(hostname) >= 7 and hostname[:7] == 'derecho':
        host = 'derecho'
    elif len(hostname) >= 6 and hostname[:6] == 'casper':
        host = 'casper'
    elif len(hostname) >= 6 and hostname[:6] == 'summit':
        host = 'summit'
    elif len(hostname) >= 8 and hostname[:8] == 'frontier':
        host = 'frontier'
    else: # Default to enable some initial testing on other machines such as eldorado
        host = 'derecho'
    
    print('host:', host)
    host_yml = host + '.yml'
    
    # Merge in the machine config
    machine_config_path = os.path.join(repo_root, 'tests/config/environments', environment, 'machine', host_yml)
    with open(machine_config_path) as machine_config_file:
        machine_config = yaml.load(machine_config_file, Loader=yaml.SafeLoader)
        
    print('machine_config:', machine_config)
    
    # Merge machine config into merged config
    merged_config = merge_configs(merged_config, machine_config)
    print('merged_config:', merged_config)
    
    # 4. Load the suite, if specified
    print('suite:', suite)
    
    # Is there always going to be one?  I'm thinking it should be optional, but TBD, needs discussion.
    if len(suite) > 0:
        suite_yml = suite + '.yml'
        suite_config_path = machine_config_path = os.path.join(repo_root, 'tests/test_suites', suite_yml)
        with open(suite_config_path) as suite_config_file:
            suite_config = yaml.load(suite_config_file, Loader=yaml.SafeLoader)
        
        # Merge suite config into merged config
        merged_config = merge_configs(merged_config, suite_config)
        print('merged_config (with suite):', merged_config)
        
    # 5. Merge the specified config into the merged config
    merged_config = merge_configs(merged_config, specified_config)
    print('merged_config (after final merge of the specified config):', merged_config)
    
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
    
    
def create_files_for_testcase(test_dict):
    pass


def validate_cfg(config, required_keys):
    """Validate the configuration file, making sure it contains the required keys
    
    required_keys is a list of keys, each potentially being nested and separated by periods.  Example: paths.repo_root
    """
    
    # Iterate over the "compound" keys
    for compound_key in required_keys:
        print(compound_key)
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
                print('Required key not found:', compound_key)
                exit(0)
        print('Value of', compound_key, value)
        
        
    # More validations coming...
    # Potential checks:
    #  Check that number of tests is at least one.
    #  Check that there is a .in file for each test in tutorials/examples in the repo.
    #  Maybe check that the output_dir exists or can be created?
        
