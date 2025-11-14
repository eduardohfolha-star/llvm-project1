#!/usr/bin/env bash
#===----------------------------------------------------------------------===##
#
# Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
#===----------------------------------------------------------------------===##

#
# This script performs a monolithic build of the monorepo and runs the tests of
# most projects on Linux. This should be replaced by per-project scripts that
# run only the relevant tests.
#

set -e
set -o pipefail

source .ci/utils.sh

# Configuration
readonly INSTALL_DIR="${BUILD_DIR}/install"
readonly ARTIFACTS_DIR="${MONOREPO_ROOT}/artifacts"
readonly REPRODUCERS_DIR="${ARTIFACTS_DIR}/reproducers"
readonly LIT_ARGS="-v --xunit-xml-output ${BUILD_DIR}/test-results.xml --use-unique-output-file-name --timeout=1200 --time-tests --succinct"

# Parse arguments
readonly PROJECTS="${1}"
readonly TARGETS="${2}"
readonly RUNTIMES="${3}"
readonly RUNTIME_TARGETS="${4}"
readonly RUNTIME_TARGETS_NEEDS_RECONFIG="${5}"
readonly ENABLE_CIR="${6}"


setup_environment() {
    """Configure the build environment."""
    mkdir -p "${REPRODUCERS_DIR}"
    
    # Make sure any clang reproducers will end up as artifacts
    export CLANG_CRASH_DIAGNOSTICS_DIR="${REPRODUCERS_DIR}"
    
    # Set the system llvm-symbolizer as preferred
    export LLVM_SYMBOLIZER_PATH
    LLVM_SYMBOLIZER_PATH=$(which llvm-symbolizer)
    if [[ ! -f "${LLVM_SYMBOLIZER_PATH}" ]]; then
        echo "Warning: llvm-symbolizer not found!"
    fi
}


run_cmake_configure() {
    """Run CMake configuration."""
    start-group "CMake Configuration"

    cmake \
        -S "${MONOREPO_ROOT}/llvm" \
        -B "${BUILD_DIR}" \
        -D LLVM_ENABLE_PROJECTS="${PROJECTS}" \
        -D LLVM_ENABLE_RUNTIMES="${RUNTIMES}" \
        -G Ninja \
        -D CMAKE_PREFIX_PATH="${HOME}/.local" \
        -D CMAKE_BUILD_TYPE=Release \
        -D CLANG_ENABLE_CIR="${ENABLE_CIR}" \
        -D LLVM_ENABLE_ASSERTIONS=ON \
        -D LLVM_BUILD_EXAMPLES=ON \
        -D COMPILER_RT_BUILD_LIBFUZZER=OFF \
        -D LLVM_LIT_ARGS="${LIT_ARGS}" \
        -D LLVM_ENABLE_LLD=ON \
        -D CMAKE_CXX_FLAGS=-gmlt \
        -D CMAKE_C_COMPILER_LAUNCHER=sccache \
        -D CMAKE_CXX_COMPILER_LAUNCHER=sccache \
        -D LIBCXX_CXX_ABI=libcxxabi \
        -D MLIR_ENABLE_BINDINGS_PYTHON=ON \
        -D LLDB_ENABLE_PYTHON=ON \
        -D LLDB_ENFORCE_STRICT_TEST_REQUIREMENTS=ON \
        -D CMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
        -D CMAKE_EXE_LINKER_FLAGS="-no-pie" \
        -D LLVM_ENABLE_WERROR=ON
}


build_main_targets() {
    """Build the main project targets."""
    start-group "Build Main Targets"

    # Targets are not escaped as they are passed as separate arguments
    ninja -C "${BUILD_DIR}" -k 0 ${TARGETS} |& tee "${MONOREPO_ROOT}/ninja.log"
    cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja.ninja_log"
}


build_runtime_targets() {
    """Build runtime targets if specified."""
    if [[ -n "${RUNTIME_TARGETS}" ]]; then
        start-group "Build Runtime Targets"
        ninja -C "${BUILD_DIR}" ${RUNTIME_TARGETS} |& tee "${MONOREPO_ROOT}/ninja_runtimes.log"
        cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja_runtimes.ninja_log"
    fi
}


build_runtimes_with_reconfig() {
    """Build runtimes that need reconfiguration with different settings."""
    if [[ -n "${RUNTIME_TARGETS_NEEDS_RECONFIG}" ]]; then
        build_runtimes_cpp26
        build_runtimes_clang_modules
    fi
}


build_runtimes_cpp26() {
    """Build runtimes with C++26 standard."""
    start-group "Reconfigure for C++26"
    
    cmake \
        -D LIBCXX_TEST_PARAMS="std=c++26" \
        -D LIBCXXABI_TEST_PARAMS="std=c++26" \
        "${BUILD_DIR}"

    start-group "Build Runtimes with C++26"
    ninja -C "${BUILD_DIR}" ${RUNTIME_TARGETS_NEEDS_RECONFIG} |& tee "${MONOREPO_ROOT}/ninja_runtimes_cpp26.log"
    cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja_runtimes_cpp26.ninja_log"
}


build_runtimes_clang_modules() {
    """Build runtimes with Clang modules."""
    start-group "Reconfigure for Clang Modules"
    
    cmake \
        -D LIBCXX_TEST_PARAMS="enable_modules=clang" \
        -D LIBCXXABI_TEST_PARAMS="enable_modules=clang" \
        "${BUILD_DIR}"

    start-group "Build Runtimes with Clang Modules"
    ninja -C "${BUILD_DIR}" ${RUNTIME_TARGETS_NEEDS_RECONFIG} |& tee "${MONOREPO_ROOT}/ninja_runtimes_clang_modules.log"
    cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja_runtimes_clang_modules.ninja_log"
}


main() {
    """Main build function."""
    echo "Starting monolithic Linux build..."
    echo "Projects: ${PROJECTS}"
    echo "Targets: ${TARGETS}"
    echo "Runtimes: ${RUNTIMES}"
    echo "Enable CIR: ${ENABLE_CIR}"

    setup_environment
    run_cmake_configure
    build_main_targets
    build_runtime_targets
    build_runtimes_with_reconfig

    echo "Monolithic Linux build completed successfully!"
}


# Run main function
main "$@"
