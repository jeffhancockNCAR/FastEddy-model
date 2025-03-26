import os
import xarray as xr
import numpy as np

# Define directories
ref_dir = "/glade/work/ishitas/FastEddy/ref_output"
mod_dir = "/glade/work/ishitas/FastEddy/mod_output_randomized"  # New directory for modified outputs

os.makedirs(mod_dir, exist_ok=True)

def add_random_variation(data_array, scale=0.05):
    """Add a small random perturbation (±scale * original value) to a DataArray."""
    noise = np.random.uniform(-scale, scale, data_array.shape) * data_array
    return data_array + noise

# Process all NetCDF files in ref_output
for filename in os.listdir(ref_dir):
    if filename.endswith(".nc") or filename.startswith("FE_CBL"):  # Ensure we only process NetCDF files
        ref_file = os.path.join(ref_dir, filename)
        mod_file = os.path.join(mod_dir, filename)

        # Open reference dataset
        ref_ds = xr.open_dataset(ref_file)

        # Create a modified dataset with small variations
        mod_ds = ref_ds.copy(deep=True)

        # Apply random perturbations only to variables that have "zIndex"
        for var in mod_ds.variables:
            if "zIndex" in mod_ds[var].dims and "time" in mod_ds[var].dims:
                print(f"🔹 Modifying {var} in {filename}")
                mod_ds[var].values = add_random_variation(mod_ds[var].values)

        # Save modified dataset
        mod_ds.to_netcdf(mod_file)
        print(f"✅ Saved modified dataset: {mod_file}")

print("\n🎉 All modified NetCDF files have been generated in 'mod_output_randomized/'!")

