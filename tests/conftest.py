import pytest

def pytest_addoption(parser):
    parser.addoption("--output-dir", action="store", default="/glade/work/ishitas/FastEddy/mod_output", help="Directory where model outputs are stored")
    parser.addoption("--ref-dir", action="store", default="/glade/work/ishitas/FastEddy/ref_output", help="Directory where model outputs are stored")

@pytest.fixture
def output_dirs(request):
    """Retrieve ref_output and mod_output directories."""
    ref_dir = request.config.getoption("--ref-dir")
    mod_dir = request.config.getoption("--output-dir")
    return ref_dir, mod_dir

