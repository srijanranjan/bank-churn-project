import subprocess
import sys
from pathlib import Path

PIPELINE_STAGES = [
    "01_ingest_validate.py",
    "02_clean_segment.py",
    "03_load_to_sqlite.py",
    "04_churn_distribution.py",
    "05_demographic_analysis.py",
    "06_high_value_churn.py",
]

SCRIPTS_DIR = Path(__file__).parent


def run_stage(script_name: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*60}")

    result = subprocess.run([sys.executable, str(script_path)])

    if result.returncode != 0:
        print(f"\n[PIPELINE STOPPED] '{script_name}' failed with exit code {result.returncode}.")
        sys.exit(result.returncode)


def main():
    print("Starting European Bank Churn Analytics pipeline...\n")
    for stage in PIPELINE_STAGES:
        run_stage(stage)

    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE — all stages ran successfully.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()