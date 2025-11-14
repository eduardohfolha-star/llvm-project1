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
# most projects on Windows. This should be replaced by per-project scripts that
# run only the relevant tests.
#

set -e
set -o pipefail

source .ci/utils.sh

# Parse arguments
readonly PROJECTS="${1}"
readonly TARGETS="${2}"
readonly RUNTIMES="${3}"
readonly RUNTIMES_TARGETS="${4}"


setup_windows_environment() {
    """Configure Windows-specific build environment."""
    start-group "Environment Setup"
    
    pip install -q -r "${MONOREPO_ROOT}/.ci/all_requirements.txt"

    # Set compiler and linker
    export CC="C:/clang/clang-msvc/bin/clang-cl.exe"
    export CXX="C:/clang/clang-msvc/bin/clang-cl.exe" 
    export LD="link"
}


run_windows_cmake_configure() {
    """Run CMake configuration for Windows."""
    start-group "CMake Configuration"

    # The CMAKE_*_LINKER_FLAGS to disable the manifest come from research
    # on fixing a build reliability issue on the build server, please
    # see https://github.com/llvm/llvm-project/pull/82393 and
    # https://discourse.llvm.org/t/rfc-future-of-windows-pre-commit-ci/76840/40
    # for further information.
    cmake \
        -S "${MONOREPO_ROOT}/llvm" \
        -B "${BUILD_DIR}" \
        -D LLVM_ENABLE_PROJECTS="${PROJECTS}" \
        -G Ninja \
        -D CMAKE_BUILD_TYPE=Release \
        -D LLVM_ENABLE_ASSERTIONS=ON \
        -D LLVM_BUILD_EXAMPLES=ON \
        -D COMPILER_RT_BUILD_LIBFUZZER=OFF \
        -D LLVM_LIT_ARGS="-v --xunit-xml-output ${BUILD_DIR}/test-results.xml --use-unique-output-file-name --timeout=1200 --time-tests --succinct" \
        -D COMPILER_RT_BUILD_ORC=OFF \
        -D CMAKE_C_COMPILER_LAUNCHER=sccache \
        -D CMAKE_CXX_COMPILER_LAUNCHER=sccache \
        -D MLIR_ENABLE_BINDINGS_PYTHON=ON \
        -D CMAKE_EXE_LINKER_FLAGS="/MANIFEST:NO" \
        -D CMAKE_MODULE_LINKER_FLAGS="/MANIFEST:NO" \
        -D CMAKE_SHARED_LINKER_FLAGS="/MANIFEST:NO" \
        -D LLVM_ENABLE_RUNTIMES="${RUNTIMES}"
}


build_windows_main_targets() {
    """Build main targets on Windows."""
    start-group "Build Main Targets"

    # Targets are not escaped as they are passed as separate arguments
    ninja -C "${BUILD_DIR}" -k 0 ${TARGETS} |& tee "${MONOREPO_ROOT}/ninja.log"
    cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja.ninja_log"
}


build_windows_runtime_targets() {
    """Build runtime targets on Windows if specified."""
    if [[ -n "${RUNTIMES_TARGETS}" ]]; then
        start-group "Build Runtime Targets"
        ninja -C "${BUILD_DIR}" -k 0 ${RUNTIMES_TARGETS} |& tee "${MONOREPO_ROOT}/ninja_runtimes.log"
        cp "${BUILD_DIR}/.ninja_log" "${MONOREPO_ROOT}/ninja_runtimes.ninja_log"
    fi
}


main() {
    """Main build function for Windows."""
    echo "Starting monolithic Windows build..."
    echo "Projects: ${PROJECTS}"
    echo "Targets: ${TARGETS}" 
    echo "Runtimes: ${RUNTIMES}"
    echo "Runtime Targets: ${RUNTIMES_TARGETS}"

    setup_windows_environment
    run_windows_cmake_configure
    build_windows_main_targets
    build_windows_runtime_targets

    echo "Monolithic Windows build completed successfully!"
}


# Run main function
main "$@"
