# utils/compiler.py

import os
import subprocess

class Compiler:
    @staticmethod
    def compile_fasteddy(repo_root: str, logger=None) -> bool:
        """
        Compile FastEddy from FEMAIN directory.
        Returns True on success, False otherwise.
        """
        make_dir = os.path.join(repo_root, "SRC", "FEMAIN")
        logger.info(f"[Compile] Compiling FastEddy in: {make_dir}")

        compile_cmd = "module load cuda && make clean && make"

        try:
            result = subprocess.run(
                compile_cmd,
                shell=True,
                cwd=make_dir,
                executable="/bin/bash",  # ensures `module` command is available
                check=True
            )
            logger.info("[Compile] Success.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[Compile] FAILED with return code {e.returncode}")
            return False
        except FileNotFoundError:
            logger.error(f"[Compile] ERROR: Directory not found: {make_dir}")
            return False

