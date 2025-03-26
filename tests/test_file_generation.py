import os
import pytest

@pytest.fixture
def output_dirs(request):
    """Fixture to retrieve ref_output and mod_output directories."""
    ref_dir = request.config.getoption("--ref-dir")
    mod_dir = request.config.getoption("--output-dir")
    return ref_dir, mod_dir

def test_file_count(output_dirs):
    """Check if exactly 10 time step files are generated."""
    ref_dir, mod_dir = output_dirs
    ref_files = sorted([f for f in os.listdir(ref_dir) if f.startswith("FE_CBL.")])
    mod_files = sorted([f for f in os.listdir(mod_dir) if f.startswith("FE_CBL.")])

    assert len(mod_files) == 6, f"Expected 10 files, found {len(mod_files)}"
    assert ref_files == mod_files, f"File names do not match!\nReference: {ref_files}\nModel: {mod_files}"
