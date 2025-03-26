import os
import pytest
import xarray as xr

@pytest.mark.parametrize("filename", [f"FE_CBL.{2*i}" for i in range(6)])
def test_netcdf_structure(output_dirs, filename):
    """Ensure NetCDF variables and dimensions are identical in reference vs. model output."""
    ref_dir, mod_dir = output_dirs
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
