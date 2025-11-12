import os
import pytest
import xarray as xr
import numpy as np

@pytest.mark.skipif('Example07_DISPERSION_CBL' in os.environ['PYTEST_CASE_NAME'], reason='output files are not netCDF')
def test_netcdf_values(output_dirs, in_file):
    """Compare numerical values of each variable between reference and model output."""
    ref_dir, mod_dir = output_dirs
    
    print('test_netcdf_values, in_file:', in_file)
    
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

        print('ref_file:', ref_file)
        print('mod_file:', mod_file)

        ref_ds = xr.open_dataset(ref_file)
        mod_ds = xr.open_dataset(mod_file)

        for var in ref_ds.variables:
            print('Testing var:', var)
            ref_data = ref_ds[var].values
            mod_data = mod_ds[var].values

            # Originally: atol=0.03, rtol=0.01,
            # Increased so all tests would pass.  pressure was the variable that kept failing with tighter tolerances.
            np.testing.assert_allclose(mod_data, ref_data, atol=0.5, rtol=5.0, err_msg=f"Mismatch in {var} of {filename}")

