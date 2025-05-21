import os, sys, argparse
from jinja2 import Environment, FileSystemLoader
from utils.setup_config import load_and_merge_config, validate_cfg
#from utils.compiler import Compiler
#from utils.executor import Executor

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--config", required=True)
    p.add_argument("-s", "--suite", choices=["minimal","comprehensive"], default="minimal")
    p.add_argument("--no-compile", action="store_true")
    p.add_argument("-t", "--test-case")
    return p.parse_args()

def main():
    args = parse_args()

    # 1. Load & validate config
    cfg = load_and_merge_config(args.config, args.suite)
    validate_cfg(cfg, required_keys=[
        "paths.repo_root","compile.enabled","execution.pbs",
        "execution.mpi_ranks","test_cases"
    ])

    # 2. Optional compile
    if cfg["compile"]["enabled"] and not args.no_compile:
        if not Compiler.compile_fasteddy(cfg["paths"]["repo_root"]):
            sys.exit("Compilation failed – aborting.")

    # 3. Load test suite
    #suite_cfg = load_yaml(f"tests/test_suites/{args.suite}.yml")
    #test_cases = suite_cfg["test_cases"]
    test_cases = cfg["test_cases"]
    if args.test_case:
        test_cases = [tc for tc in test_cases if tc["name"] == args.test_case]

    # 4. Prepare Jinja
    tpl_dir = os.path.join(os.path.dirname(__file__), "utils", "templates")
    jenv = Environment(loader=FileSystemLoader(tpl_dir), trim_blocks=True, lstrip_blocks=True)
    tpl = jenv.get_template("pbs_job.sh.j2")

    results = []
    workdir = os.path.abspath("fasteddy_work")
    os.makedirs(workdir, exist_ok=True)

    # 5. Loop over cases
    for tc in test_cases:
        script = tpl.render(pbs=cfg["execution"]["pbs"],
                            paths=cfg["paths"],
                            execution=cfg["execution"],
                            test_case=tc)
        script_path = os.path.join(workdir, f"run_{tc['name']}.sh")
        with open(script_path, "w") as f: f.write(script)
        os.chmod(script_path, 0o755)

        Executor.submit_and_wait(script_path)
        Executor.collect_outputs(tc, cfg)
        res = Executor.run_pytest(tc, cfg)
        results.append(res)

    # 6. Aggregate & report
    summary = Executor.aggregate_results(results)
    print(summary)

if __name__ == "__main__":
    main()

