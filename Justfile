set shell := ["bash", "-uc"]

# List available project commands.
default:
    @just --list

# Verify all committed pins and the frozen 18-task selection.
check:
    python3 scripts/lab.py check

# Fetch pinned CVDP inputs and build the baseline/treatment images.
bootstrap: check
    python3 scripts/bootstrap.py --all --verify
    python3 scripts/lab.py harbor-bootstrap

# Rebuild and verify the pinned arm images.
build-images:
    python3 scripts/build_images.py

# Materialize one frozen CVDP task as a Harbor task.
materialize task arm:
    python3 scripts/lab.py materialize "{{task}}" "{{arm}}"

# Run the offline test suite.
test: check
    python3 -m unittest discover -s tests -v

# Print a resolved Harbor job without running agents.
dry-run selector="smoke":
    python3 scripts/lab.py job --selector "{{selector}}" --dry-run

# Check host, credentials, images, and a resolved selection.
preflight selector="smoke":
    python3 scripts/lab.py preflight --selector "{{selector}}"

# Run a selected matrix through pinned Harbor.
run tasks="all" models="all" arms="all" attempts="1" name="experiment":
    python3 scripts/lab.py run --tasks "{{tasks}}" --models "{{models}}" --arms "{{arms}}" --attempts "{{attempts}}" --name "{{name}}"

# Run exactly the required four-trial smoke experiment.
smoke:
    python3 scripts/lab.py run --selector smoke --name smoke

# Show normalized status for a run ID or latest.
status run="latest":
    python3 scripts/lab.py status "{{run}}"

# Regenerate compact analysis for a run ID or latest.
analyze run="latest":
    python3 scripts/lab.py analyze "{{run}}"
