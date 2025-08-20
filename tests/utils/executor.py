# utils/executor.py

import os
import time
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


class Executor:
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.scheduler = cfg.get("scheduler", "pbs")
        self.repo_root = cfg["paths"]["repo_root"]
        self.output_dir = os.path.expandvars(cfg["paths"]["output_dir"])
        self.template_dir = os.path.join(self.repo_root, "tests", "templates")
        self.logger = logger

        self.jenv = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self.template_map = {
            "pbs": "pbs_job.sh.j2",
            "slurm": "slurm_job.sh.j2",
        }

        # case_name -> metadata
        self.job_status = {}
        self.test_cases_dict = {
            name: case_cfg for tc in cfg["test_cases"] for name, case_cfg in tc.items()
        }

        # Tuning knobs (can also come from cfg["execution"])
        exe_cfg = self.cfg.get("execution", {})
        self.quiet_window_seconds = int(exe_cfg.get("quiet_window_seconds", 20))
        self.poll_interval = int(exe_cfg.get("poll_interval", 30))
        self.startup_timeout = int(exe_cfg.get("startup_timeout", 60))
        self.missing_grace_polls = int(exe_cfg.get("missing_grace_polls", 3))

    # -------------------------
    # Public API
    # -------------------------

    def run_test_case(self, case_name, case_cfg):
        case_dir = os.path.join(self.output_dir, case_name)
        os.makedirs(case_dir, exist_ok=True)

        input_basename = self.prepare_input_file(case_name, case_cfg)
        case_cfg["input_file"] = input_basename  # template will pick this up

        script_name = f"{case_name}.{self.scheduler}"
        script_path = os.path.join(case_dir, script_name)

        job_script = self._render_template(case_name, case_cfg)
        with open(script_path, "w") as f:
            f.write(job_script)
        self._log_info(f"[Executor] Job script written: {script_path}")

        self._submit_job(script_path, case_name)

    def wait_for_jobs(self):
        self._print("[Executor] Waiting for jobs to enter queue...")

        # --- Ensure each job appears at least once ---
        for case_name, meta in self.job_status.items():
            jid = meta.get("job_id")
            if not jid:
                continue
            start = time.time()
            while True:
                st = self._pbs_safe_state(jid) if self.scheduler == "pbs" else self._slurm_job_state(jid)
                if st not in ("MISSING", None):
                    break
                if time.time() - start > self.startup_timeout:
                    self._print(f"[Executor] Timeout: job {jid} never appeared in queue.")
                    break
                self._print(f"[Executor] Waiting for job {jid} to appear...")
                time.sleep(5)

        self._print("[Executor] Monitoring job completion...")

        terminal_slurm = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"}

        # Track consecutive "missing" polls for PBS to avoid early exit on transient MISSING
        for meta in self.job_status.items():
            pass  # keep dict intact
        for meta in self.job_status.values():
            meta["missing_polls"] = 0
            meta["finished"] = False

        while True:
            still_running = []

            for case_name, meta in self.job_status.items():
                if meta.get("status") != "submitted":
                    continue
                jid = meta.get("job_id")
                if not jid:
                    continue

                if self.scheduler == "pbs":
                    st = self._pbs_safe_state(jid)
                    if st == "F":
                        meta["finished"] = True
                    elif st in {"Q", "R", "H", "S", "E", "UNKNOWN"}:
                        # UNKNOWN -> conservative: treat as active
                        still_running.append(case_name)
                        meta["missing_polls"] = 0
                    elif st == "MISSING":
                        # Require several consecutive MISSINGs before considering done
                        meta["missing_polls"] += 1
                        if meta["missing_polls"] < self.missing_grace_polls:
                            still_running.append(case_name)
                        # else: allow to fall through to quiescence gate
                    else:
                        # Any odd state: conservative = active
                        still_running.append(case_name)
                        meta["missing_polls"] = 0

                else:  # SLURM
                    st = self._slurm_job_state(jid)
                    if st in terminal_slurm or st is None:  # None => not in sacct/squeue; possibly done
                        meta["finished"] = True
                    else:
                        still_running.append(case_name)

            if still_running:
                self._print(f"[Executor] Still running: {', '.join(still_running)}")
                time.sleep(self.poll_interval)
            else:
                break

        # Quiescence check: require output dirs to be quiet
        self._print("[Executor] Stabilizing outputs (quiescence check)...")
        while True:
            not_quiet = []
            for case_name, meta in self.job_status.items():
                if meta.get("status") != "submitted":
                    continue
                case_out_dir = os.path.join(self.output_dir, case_name, "output")
                if not self._dir_quiet(case_out_dir, self.quiet_window_seconds):
                    not_quiet.append(case_name)
            if not not_quiet:
                break
            self._print(f"[Executor] Waiting for quiet output: {', '.join(not_quiet)}")
            time.sleep(5)

        # Finalize metadata
        for case_name, job in self.job_status.items():
            if job["status"] == "submitted":
                jid = job.get("job_id")
                if self.scheduler == "pbs":
                    final_state, exit_code = self._pbs_final_state_and_exit(jid)
                else:
                    final_state, exit_code = self._slurm_final_state_and_exit(jid)
                job["final_state"] = final_state or "UNKNOWN"
                if exit_code is not None:
                    job["exit_code"] = exit_code
                job["status"] = "completed"

        self._print("[Executor] All jobs completed.")

    def run_pytest_for_case(self, case_name, case_cfg):
        output_path = os.path.join(self.output_dir, case_name, "output")
        os.makedirs(output_path, exist_ok=True)

        ref_dir = case_cfg.get("pytest_ref_dir")
        report_file = case_cfg.get("pytest_report_name", f"{case_name}_report.html")

        if not ref_dir:
            self._log_info(f"[Pytest] Skipping test case {case_name} – no reference dir specified.")
            return

        self._print(f"[Pytest] Running regression test for: {case_name}")

        cmd = [
            "pytest",
            "tests",  # runs repo_root/tests
            "--output-dir", output_path,
            "--ref-dir", ref_dir,
            "--html", os.path.join(output_path, report_file),
        ]

        try:
            subprocess.run(cmd, check=True, cwd=self.repo_root)
            self._print(f"[Pytest] {case_name} PASSED")
        except subprocess.CalledProcessError:
            self._print(f"[Pytest] {case_name} FAILED")

    def run_all_pytests(self):
        for case_name, meta in self.job_status.items():
            if meta.get("status") == "completed":
                case_cfg = self.test_cases_dict[case_name]
                # Optional: only run pytest if exit_code indicates success
                exit_code = meta.get("exit_code")
                # PBS exit code is a single int; Slurm is like "0:0"
                if exit_code is not None:
                    if ":" in str(exit_code):
                        ok = str(exit_code).split(":")[0] in {"0", "0.0"}
                    else:
                        ok = str(exit_code) == "0"
                    if not ok:
                        self._log_info(f"[Pytest] Skipping {case_name} due to non-zero exit code: {exit_code}")
                        continue
                self.run_pytest_for_case(case_name, case_cfg)

    def prepare_input_file(self, case_name, case_cfg):
        """
        Copy and edit the FastEddy input file for this test case.
        Writes to the CASE OUTPUT DIR. Returns the basename of the created input file.
        """
        tutorials_dir = os.path.join(self.repo_root, "tutorials")
        examples_dir = os.path.join(tutorials_dir, "examples")
        case_dir = os.path.join(self.output_dir, case_name)

        src_input_name = case_cfg.get("input_file", f"{case_name}.in")
        src_file = os.path.join(examples_dir, src_input_name)

        timesteps = case_cfg.get("timesteps", self.cfg.get("timesteps"))
        outputfreq = case_cfg.get("outputfreq", self.cfg.get("outputfreq"))
        batchsteps = case_cfg.get("batchsteps", self.cfg.get("batchsteps"))

        dst_basename = f"{case_name}_{timesteps if timesteps is not None else 'X'}steps.in"
        dst_file = os.path.join(case_dir, dst_basename)

        if not os.path.exists(src_file):
            raise FileNotFoundError(f"[Executor] Input file not found: {src_file}")

        with open(src_file, "r") as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            s = line.strip()
            if s.startswith("frqOutput"):
                line = f"frqOutput = {outputfreq}  # set by test suite\n"
            elif s.startswith("Nt "):
                line = f"Nt = {timesteps}  # set by test suite\n"
            elif s.startswith("NtBatch"):
                line = f"NtBatch = {batchsteps}  # set by test suite\n"
            elif s.startswith("outPath"):
                final_out_path = os.path.join(case_dir, "output/")
                os.makedirs(final_out_path, exist_ok=True)
                line = f"outPath = {final_out_path}  # overridden by test suite\n"
                self._log_info(f"[Executor] Created output directory: {final_out_path}")
            updated_lines.append(line)

        with open(dst_file, "w") as f:
            f.writelines(updated_lines)

        self._log_info(f"[Executor] Prepared input file: {dst_file}")
        return dst_basename

    # -------------------------
    # Template & submission
    # -------------------------

    def _render_template(self, case_name, case_cfg):
        tpl_name = self.template_map.get(self.scheduler)
        if tpl_name is None:
            raise ValueError(f"Unsupported scheduler: {self.scheduler}")

        tpl = self.jenv.get_template(tpl_name)

        merged_test_case = {
            "name": case_name,
            "base_name": case_name,
            "input_file": case_cfg.get("input_file", f"{case_name}.in"),
            **case_cfg,
        }

        context = {
            "pbs": self.cfg.get("execution", {}).get("pbs", {}),
            "slurm": self.cfg.get("execution", {}).get("slurm", {}),
            "paths": {
                **self.cfg.get("paths", {}),
                "src_subdir": "SRC/FEMAIN",
                "tutorials_subdir": "tutorials",
            },
            "execution": {
                **self.cfg.get("execution", {}),
                "timesteps": merged_test_case.get("timesteps", self.cfg.get("timesteps")),
                "outputfreq": merged_test_case.get("outputfreq", self.cfg.get("outputfreq")),
                "batchsteps": merged_test_case.get("batchsteps", self.cfg.get("batchsteps")),
                "copy_examples": True,
            },
            "test_case": merged_test_case,
        }

        return tpl.render(context)

    def _submit_job(self, script_path, case_name):
        submit_cmd = {
            "pbs": ["qsub", script_path],
            "slurm": ["sbatch", script_path],
        }.get(self.scheduler)

        try:
            result = subprocess.run(submit_cmd, check=True, stdout=subprocess.PIPE, text=True)
            raw_output = result.stdout.strip()

            if self.scheduler == "pbs":
                job_id = raw_output.split(".")[0]  # e.g., "2316876.derecho.ucar.edu" -> "2316876"
                stdout_path = os.path.join(self.output_dir, case_name, f"{case_name}.o{job_id}")
            elif self.scheduler == "slurm":
                job_id = raw_output.strip().split()[-1]  # e.g., "Submitted batch job 789123" -> "789123"
                stdout_path = os.path.join(self.output_dir, case_name, f"slurm-{job_id}.out")
            else:
                raise ValueError(f"Unsupported scheduler: {self.scheduler}")

            self.job_status[case_name] = {
                "job_id": job_id,
                "status": "submitted",
                "stdout_path": stdout_path,
            }
            self._log_info(f"[Executor] Submitted job for {case_name}: {job_id}")
            return job_id

        except subprocess.CalledProcessError as e:
            self._log_error(f"[Executor] Job submission failed for {case_name}: {e}")
            self.job_status[case_name] = {"job_id": None, "status": "failed"}
            return None

    # -------------------------
    # Scheduler helpers
    # -------------------------

    def _pbs_safe_state(self, job_id):
        """
        Robustly ask PBS for job_state.
        Returns one of {'Q','R','H','S','E','F','UNKNOWN'} or 'MISSING' if qstat can't see the job.
        Retries once to avoid transient lookup glitches.
        """
        def _one():
            try:
                out = subprocess.check_output(
                    ["qstat", "-xf", job_id],
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            except subprocess.CalledProcessError:
                return "MISSING"
            for line in out.splitlines():
                if line.strip().startswith("job_state ="):
                    return line.split("=", 1)[1].strip() or "UNKNOWN"
            return "UNKNOWN"

        st = _one()
        if st == "MISSING":
            time.sleep(2)
            st = _one()
        return st

    def _pbs_job_state(self, job_id):
        # kept for compatibility
        return self._pbs_safe_state(job_id)

    def _pbs_final_state_and_exit(self, job_id):
        """Returns (final_state, exit_code_str|None)."""
        try:
            out = subprocess.check_output(
                ["qstat", "-xf", job_id],
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError:
            return (None, None)

        final_state, exit_code = None, None
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("job_state ="):
                final_state = s.split("=", 1)[1].strip()
            elif s.startswith("Exit_status ="):
                exit_code = s.split("=", 1)[1].strip()
        return (final_state, exit_code)

    def _slurm_job_state(self, job_id):
        """
        Return SLURM state (COMPLETED, FAILED, CANCELLED, TIMEOUT, RUNNING, PENDING, etc.),
        "PENDING_OR_RUNNING" when only squeue sees it, or None if not found.
        """
        try:
            out = subprocess.check_output(
                ["sacct", "-j", job_id, "--format=JobID,State", "-n", "-P"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in out.splitlines():
                parts = line.strip().split("|", 1)
                if not parts:
                    continue
                jid_field = parts[0]
                state = parts[1] if len(parts) > 1 else ""
                if jid_field.split(".")[0] == job_id:
                    return state.split()[0] if state else "UNKNOWN"
        except subprocess.CalledProcessError:
            pass

        try:
            ret = subprocess.run(
                ["squeue", "-j", job_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ret.returncode == 0:
                return "PENDING_OR_RUNNING"
        except Exception:
            pass

        return None

    def _slurm_final_state_and_exit(self, job_id):
        """Returns (final_state, exit_code_str|None) using sacct."""
        try:
            out = subprocess.check_output(
                ["sacct", "-j", job_id, "--format=JobID,State,ExitCode", "-n", "-P"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in out.splitlines():
                parts = line.strip().split("|")
                if len(parts) < 3:
                    continue
                jid_field, state, exit_code = parts[0], parts[1], parts[2]
                if jid_field.split(".")[0] == job_id:
                    return (state.split()[0] if state else "UNKNOWN", exit_code)
        except subprocess.CalledProcessError:
            pass
        return (None, None)

    # -------------------------
    # Quiescence helper
    # -------------------------

    def _dir_quiet(self, directory, quiet_window):
        """
        Returns True if directory doesn't exist (treat as quiet) OR
        if the newest mtime under it is older than quiet_window seconds.
        """
        p = Path(directory)
        if not p.exists():
            return True
        newest = 0.0
        try:
            for root, _, files in os.walk(p):
                for f in files:
                    try:
                        m = os.path.getmtime(os.path.join(root, f))
                        if m > newest:
                            newest = m
                    except FileNotFoundError:
                        continue
        except Exception:
            return False

        return (time.time() - newest) >= quiet_window

    # -------------------------
    # Logging helpers
    # -------------------------

    def _log_info(self, msg):
        if self.logger:
            self.logger.info(msg)
        else:
            print(msg)

    def _log_error(self, msg):
        if self.logger:
            self.logger.error(msg)
        else:
            print(msg)

    def _print(self, msg):
        print(msg)

