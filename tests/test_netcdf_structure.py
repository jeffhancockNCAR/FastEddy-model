import os
import pytest
import xarray as xr

def test_netcdf_structure(output_dirs, in_file):
    """Ensure NetCDF variables and dimensions are identical in reference vs. model output."""
    ref_dir, mod_dir = output_dirs
    
    print('test_netcdf_structure, in_file:', in_file)
    
    # Open the in_file for read, and get the needed parameters, which are:
    # outFileBase
    # Nt
    # frqOutput
    # The last two determine how many output files there will be and their time steps, which are part of their filenames
    print('in_file:', in_file)
    
    with open(in_file, "r") as f:
        lines = f.readlines()

    Nt = 10                # a default
    frqOutput = 2          # a default
    outFileBase = 'FE_CBL' # a default
    
    for line in lines:
        s = line.strip()
        if s.startswith("frqOutput"):
            value = line.split('=')[1] # The part after the =
            value = value.split('#')[0] # The part before the #
            frqOutput = int(value)
        elif s.startswith("Nt "): # The space is important to distinguish it from NtBatch!
            value = line.split('=')[1] # The part after the =
            value = value.split('#')[0] # The part before the #
            Nt = int(value)
        elif s.startswith("outFileBase"):
            value = line.split('=')[1] # The part after the =
            value = value.split('#')[0] # The part before the #
            outFileBase = value.strip()
    
    # Now iterate over expected output files
    # Expected time step suffixes go from 0 to Nt by step frqOutput
    for i in [i * frqOutput for i in range(int(Nt/frqOutput) + 1)]:
        filename = outFileBase + '.' + str(i)
        print('filename:', filename)
    
        ref_file = os.path.join(ref_dir, filename)
        mod_file = os.path.join(mod_dir, filename)

        assert os.path.exists(mod_file), f"Missing file: {mod_file}"

        ref_ds = xr.open_dataset(ref_file)
        mod_ds = xr.open_dataset(mod_file)

        # Compare dimensions
        assert ref_ds.dims == mod_ds.dims, f"Dimension mismatch in {filename}: {ref_ds.dims} vs {mod_ds.dims}"

        # Compare variables
        assert set(ref_ds.variables.keys()) == set(mod_ds.variables.keys()), \
            f"Variable mismatch in {filename}: {set(ref_ds.variables.keys())} vs {set(mod_ds.variables.keys())}"
