import os
import pytest
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_squared_error


def plot_difference_map(ref_ds, mod_ds, var_name, filename):
    """Plot spatial difference (mod - ref) as a heatmap for a given variable at the last time step."""
    if "zIndex" not in ref_ds[var_name].dims or "time" not in ref_ds[var_name].dims:
        print(f"⚠️ Skipping {var_name} in {filename} (missing required dimensions: time, zIndex)")
        return
    
    ref_var = ref_ds[var_name].isel(time=-1).mean(dim="zIndex", skipna=True)
    mod_var = mod_ds[var_name].isel(time=-1).mean(dim="zIndex", skipna=True)

    diff = mod_var - ref_var  # Compute differences

    plt.figure(figsize=(10, 6))
    plt.pcolormesh(diff, cmap="coolwarm", shading="auto")
    plt.colorbar(label=f"Difference in {var_name}")
    plt.title(f"Difference Map: {var_name} (mod - ref) at last timestep")
    plt.xlabel("X Index")
    plt.ylabel("Y Index")

    os.makedirs("comparison_plots", exist_ok=True)
    plt.savefig(f"comparison_plots/{filename}_{var_name}_diffmap.png")
    plt.close()


def plot_vertical_profile(ref_ds, mod_ds, var_name, filename):
    """Plot vertical profile (zIndex vs. variable) for ref and mod at a given time and location."""
    if "zIndex" not in ref_ds[var_name].dims or "time" not in ref_ds[var_name].dims:
        print(f"⚠️ Skipping {var_name} in {filename} (missing required dimensions: time, zIndex)")
        return

    ref_profile = ref_ds[var_name].isel(time=-1, yIndex=300, xIndex=300)
    mod_profile = mod_ds[var_name].isel(time=-1, yIndex=300, xIndex=300)

    z_levels = ref_ds["zIndex"].values  # Get height levels

    plt.figure(figsize=(6, 8))
    plt.plot(ref_profile, z_levels, label="Reference", linestyle="--", color="blue")
    plt.plot(mod_profile, z_levels, label="Model", linestyle="-", color="red")

    plt.xlabel(var_name)
    plt.ylabel("Height (zIndex)")
    plt.title(f"Vertical Profile of {var_name} at timestep {filename}")
    plt.legend()
    
    os.makedirs("comparison_plots", exist_ok=True)
    plt.savefig(f"comparison_plots/{filename}_{var_name}_profile.png")
    plt.close()


def plot_difference_histogram(ref_ds, mod_ds, var_name, filename):
    """Plot histogram of (mod - ref) differences for a variable."""
    if "zIndex" not in ref_ds[var_name].dims or "time" not in ref_ds[var_name].dims:
        print(f"⚠️ Skipping {var_name} in {filename} (missing required dimensions: time, zIndex)")
        return

    ref_values = ref_ds[var_name].values.ravel()
    mod_values = mod_ds[var_name].values.ravel()
    differences = mod_values - ref_values

    plt.figure(figsize=(8, 6))
    plt.hist(differences, bins=50, color="gray", alpha=0.7, edgecolor="black")
    plt.axvline(0, color="red", linestyle="--", label="Zero Difference")
    plt.xlabel(f"Difference in {var_name}")
    plt.ylabel("Frequency")
    plt.title(f"Histogram of Differences for {var_name} in {filename}")
    plt.legend()
    
    os.makedirs("comparison_plots", exist_ok=True)
    plt.savefig(f"comparison_plots/{filename}_{var_name}_histogram.png")
    plt.close()


def plot_rmse_over_time(ref_ds, mod_ds, var_name, filename):
    """Plot RMSE over time between ref and mod outputs."""
    if "zIndex" not in ref_ds[var_name].dims or "time" not in ref_ds[var_name].dims:
        print(f"⚠️ Skipping {var_name} in {filename} (missing required dimensions: time, zIndex)")
        return

    time_values = ref_ds["time"].values
    rmse_values = []

    for t in range(len(time_values)):
        ref_t = ref_ds[var_name].isel(time=t).values.ravel()
        mod_t = mod_ds[var_name].isel(time=t).values.ravel()
        rmse_values.append(mean_squared_error(ref_t, mod_t, squared=False))  # RMSE

    plt.figure(figsize=(8, 6))
    plt.plot(time_values, rmse_values, marker="o", color="black", linestyle="-")
    plt.xlabel("Time")
    plt.ylabel(f"RMSE of {var_name}")
    plt.title(f"RMSE Over Time for {var_name} in {filename}")
    
    os.makedirs("comparison_plots", exist_ok=True)
    plt.savefig(f"comparison_plots/{filename}_{var_name}_rmse.png")
    plt.close()


@pytest.mark.parametrize("filename", [f"FE_CBL.{i*2}" for i in range(6)])
def test_netcdf_visualization(output_dirs, filename):
    """Generate multiple visualizations for model comparison."""
    ref_dir, mod_dir = output_dirs
    ref_file = os.path.join(ref_dir, filename)
    mod_file = os.path.join(mod_dir, filename)

    ref_ds = xr.open_dataset(ref_file)
    mod_ds = xr.open_dataset(mod_file)

    os.makedirs("comparison_plots", exist_ok=True)

    for var in ref_ds.variables:
        # Only process variables that have "zIndex" AND "time" in their dimensions
        if "zIndex" in ref_ds[var].dims and "time" in ref_ds[var].dims:
            print(f"📊 Processing variable: {var}")
            plot_difference_map(ref_ds, mod_ds, var, filename)
            plot_vertical_profile(ref_ds, mod_ds, var, filename)
            plot_difference_histogram(ref_ds, mod_ds, var, filename)
            plot_rmse_over_time(ref_ds, mod_ds, var, filename)

