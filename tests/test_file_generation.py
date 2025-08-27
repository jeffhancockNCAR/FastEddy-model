import os
import pytest

def test_file_count(output_dirs, in_file):
    """Check if the expected number of time step files are generated."""
    ref_dir, mod_dir = output_dirs
    
    print('test_file_count, in_file:', in_file)
    
    # Open the in_file for read, and get the needed parameter, which is:
    # outFileBase
    print('in_file:', in_file)
    
    with open(in_file, "r") as f:
        lines = f.readlines()

    outFileBase = 'FE_CBL' # a default
    
    for line in lines:
        s = line.strip()
        if s.startswith("outFileBase"):
            value = line.split('=')[1] # The part after the =
            value = value.split('#')[0] # The part before the #
            outFileBase = value.strip()
    
    ref_files = sorted([f for f in os.listdir(ref_dir) if f.startswith(outFileBase)])
    mod_files = sorted([f for f in os.listdir(mod_dir) if f.startswith(outFileBase)])

    assert len(mod_files) == len(ref_files), f"Expected {len(ref_files)} files, found {len(mod_files)}"
    assert ref_files == mod_files, f"File names do not match!\nReference: {ref_files}\nModel: {mod_files}"
