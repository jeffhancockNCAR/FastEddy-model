import os
import pytest
import xarray as xr
import numpy as np

@pytest.mark.parametrize("filename", [f"FE_CBL.{i*2}" for i in range(6)])
def test_netcdf_values(output_dirs, filename):
    """Compare numerical values of each variable between reference and model output."""
    ref_dir, mod_dir = output_dirs
    ref_file = os.path.join(ref_dir, filename)
    mod_file = os.path.join(mod_dir, filename)

    ref_ds = xr.open_dataset(ref_file)
    mod_ds = xr.open_dataset(mod_file)

    for var in ref_ds.variables:
        ref_data = ref_ds[var].values
        mod_data = mod_ds[var].values

        np.testing.assert_allclose(
            mod_data, ref_data, atol=1e-3
        ), f"Mismatch in {var} of {filename}"

