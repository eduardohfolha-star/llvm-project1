#!/usr/bin/env bash
#===----------------------------------------------------------------------===##
#
# Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
#===----------------------------------------------------------------------===##

# This script performs setup and provides utilities used by the monolithic
# build scripts (monolithic-linux.sh and monolithic-windows.sh).

set -ex
set -o pipefail

readonly MONOREPO_ROOT="${MONOREPO_ROOT:="$(git rev-parse --show-toplevel)"}"
readonly BUILD_DIR="${BUILD_DIR:=${MONOREPO_ROOT}/build}"
readonly ARTIFACTS_DIR="${MONOREPO_ROOT}/artifacts"


cleanup_previous_build() {
    """Remove previous build directory and prepare for new build."""
    echo "Cleaning up previous build..."
    rm -rf "${BUILD_DIR}"
    mkdir -p "${ARTIFACTS_DIR}"
}


initialize_build_cache() {
    """Initialize sccache and reset statistics."""
    sccache --zero-stats
    echo "sccache initialized and statistics reset"
}


collect_build_artifacts() {
    """Collect build artifacts, logs, and test results."""
    local retcode=$1
    
    echo "Collecting build artifacts (exit code: ${retcode})..."
    mkdir -p "${ARTIFACTS_DIR}"

    # SCCache statistics
    sccache --show-stats
    sccache --show-stats >> "${ARTIFACTS_DIR}/sccache_stats.txt"

    # Build logs and ninja logs
    cp "${MONOREPO_ROOT}"/*.ninja_log "${ARTIFACTS_DIR}/" 2>/dev/null || true
    cp "${MONOREPO_ROOT}"/*.log "${ARTIFACTS_DIR}/" 2>/dev/null || true

    # Test results (may not exist if build failed early)
    shopt -s nullglob
    cp "${BUILD_DIR}"/test-results.*.xml "${ARTIFACTS_DIR}/" 2>/dev/null || true
    shopt -u nullglob
    
    return $retcode
}


generate_github_ci_reports() {
    """Generate GitHub-specific test reports and advisor explanations."""
    local retcode=$1
    
    if [[ -z "$GITHUB_ACTIONS" ]]; then
        return 0
    fi

    echo "Generating GitHub CI reports..."
    
    # Generate test report for GitHub step summary
    python "${MONOREPO_ROOT}"/.ci/generate_test_report_github.py \
        $retcode "${BUILD_DIR}"/test-results.*.xml "${MONOREPO_ROOT}"/ninja*.log \
        >> "$GITHUB_STEP_SUMMARY"

    # Generate premerge advisor explanations
    python "${MONOREPO_ROOT}"/.ci/premerge_advisor_explain.py \
        $(git rev-parse HEAD~1) $retcode "${GITHUB_TOKEN}" \
        $GITHUB_PR_NUMBER "${BUILD_DIR}"/test-results.*.xml \
        "${MONOREPO_ROOT}"/ninja*.log
}


upload_failures_to_advisor() {
    """Upload failure details to premerge advisor service."""
    local retcode=$1
    
    if [[ "$retcode" == "0" ]]; then
        return 0
    fi

    echo "Uploading failure details to premerge advisor..."
    
    local commit_sha
    local run_identifier
    
    if [[ -n "$GITHUB_ACTIONS" ]]; then
        commit_sha=$(git rev-parse HEAD~1)
        run_identifier="$GITHUB_RUN_NUMBER"
    else
        commit_sha=$(git rev-parse HEAD)
        run_identifier="$BUILDBOT_BUILDNUMBER"
    fi

    python "${MONOREPO_ROOT}"/.ci/premerge_advisor_upload.py \
        "$commit_sha" "$run_identifier" \
        "${BUILD_DIR}"/test-results.*.xml "${MONOREPO_ROOT}"/ninja*.log
}


exit_handler() {
    """Global exit handler for build scripts."""
    local retcode=$?
    
    echo "Build process completed with exit code: $retcode"
    
    collect_build_artifacts $retcode
    generate_github_ci_reports $retcode
    upload_failures_to_advisor $retcode

    echo "Artifacts and reports processed successfully"
    exit $retcode
}


start_group() {
    """Start a named log group for better organization."""
    local groupname="$1"
    
    if [[ -n "$GITHUB_ACTIONS" ]]; then
        echo "::endgroup"
        echo "::group::$groupname"
    elif [[ -n "$POSTCOMMIT_CI" ]]; then
        echo "@@@$STEP@@@"
    else
        echo "=== Starting: $groupname ==="
    fi
}


install_python_dependencies() {
    """Install required Python packages for CI scripts."""
    export PIP_BREAK_SYSTEM_PACKAGES=1
    
    echo "Installing Python dependencies..."
    pip install -q -r "${MONOREPO_ROOT}"/.ci/all_requirements.txt
    
    # Verify critical dependencies are available
    python -c "import junitparser, google.cloud.storage, github" 2>/dev/null || {
        echo "Error: Failed to import required Python modules"
        return 1
    }
}


setup_lit_timing_cache() {
    """Download cached lit timing files for faster test execution."""
    # The ARM64 builders run on AWS and don't have access to the GCS cache
    if [[ -n "$GITHUB_ACTIONS" ]] && [[ "$RUNNER_ARCH" != "ARM64" ]]; then
        echo "Setting up lit timing cache..."
        python "${MONOREPO_ROOT}"/.ci/cache_lit_timing_files.py download
    else
        echo "Skipping lit timing cache setup"
    fi
}


main_setup() {
    """Main setup function called by build scripts."""
    echo "Initializing build environment..."
    
    cleanup_previous_build
    initialize_build_cache
    
    # Register global exit handler
    trap exit_handler EXIT
    
    install_python_dependencies
    setup_lit_timing_cache
    
    echo "Build environment setup completed successfully"
}


# Export functions for use in child scripts
export -f start_group
export -f exit_handler
export -f collect_build_artifacts

# If script is executed directly, run main setup
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main_setup "$@"
fi
