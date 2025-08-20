import os, sys, argparse, logging
from jinja2 import Environment, FileSystemLoader
from utils.setup_config import load_and_merge_config, validate_cfg
from utils.compiler import Compiler
from utils.executor import Executor

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--config", required=True)
    p.add_argument("-s", "--suite", choices=["minimal","comprehensive"], default="minimal")
    p.add_argument("--no-compile", action="store_true")
    p.add_argument("-t", "--test-case")
    p.add_argument("-l", "--log-file", help="Path to log file")
    return p.parse_args()

def setup_logger(log_path):
    logger = logging.getLogger("FastEddyTestSuite")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

def main():
    args = parse_args()

    log_file = args.log_file if args.log_file else "run_tests.log"
    logger = setup_logger(log_file)
    logger.info("Starting FastEddy test suite")

    # 1. Load & validate config
    cfg = load_and_merge_config(args.config, args.suite, logger=logger)
    print(cfg)
    print("Validating....")
    validate_cfg(config=cfg,
             required_keys=["paths.repo_root", "compile.enabled", "execution.pbs", "execution.mpi_ranks", "test_cases"],logger=logger)

    logger.info("Config loaded and validated.")
    
    # 2. Optional compilation
    if cfg["compile"]["enabled"] and not args.no_compile:
        from utils.compiler import Compiler
        logger.info("Compiling FastEddy...")
        success = Compiler.compile_fasteddy(cfg["paths"]["repo_root"],logger=logger)
        if not success:
            logger.error("Compilation failed. Aborting.")
            sys.exit("[RunTests] Compilation failed. Aborting.")

    
    # 3. Initialize executor
    executor = Executor(cfg, logger=logger)

    # 4. Extract relevant test cases
    test_cases = cfg["test_cases"]
    if args.test_case:
        filtered = []
        for tc in test_cases:
            for name in tc:
                if name == args.test_case:
                    filtered.append({name: tc[name]})
        if not filtered:
            logger.error(f"No test case found with name '{args.test_case}'")
            sys.exit(f"[RunTests] No test case found with name '{args.test_case}'")
        test_cases = filtered


    # 5. Run test cases
    for tc in test_cases:
        for name, case_cfg in tc.items():
            logger.info(f"Running test case: {name}")
            executor.run_test_case(name, case_cfg)

    executor.wait_for_jobs()
    executor.run_all_pytests()
    logger.info("All tests completed.")

if __name__ == "__main__":
    main()

