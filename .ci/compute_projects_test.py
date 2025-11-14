"""Tests for compute_projects.py"""

import unittest
import compute_projects


class TestComputeProjects(unittest.TestCase):
    """Test cases for project computation logic."""
    
    def _assert_env_variables(self, actual, expected_projects, expected_targets, 
                            expected_runtimes="", expected_runtime_targets="",
                            expected_runtime_reconfig="", enable_cir="OFF"):
        """Helper para verificar variáveis de ambiente."""
        self.assertEqual(actual["projects_to_build"], expected_projects)
        self.assertEqual(actual["project_check_targets"], expected_targets)
        self.assertEqual(actual["runtimes_to_build"], expected_runtimes)
        self.assertEqual(actual["runtimes_check_targets"], expected_runtime_targets)
        self.assertEqual(actual["runtimes_check_targets_needs_reconfig"], expected_runtime_reconfig)
        self.assertEqual(actual["enable_cir"], enable_cir)

    def test_llvm_modification_linux(self):
        """Test LLVM modification on Linux."""
        env_vars = compute_projects.get_env_variables(["llvm/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;clang-tools-extra;flang;lld;lldb;llvm;mlir;polly",
            "check-bolt check-clang check-clang-tools check-flang check-lld check-lldb check-llvm check-mlir check-polly",
            "libcxx;libcxxabi;libunwind",
            "",
            "check-cxx check-cxxabi check-unwind"
        )

    def test_llvm_modification_windows(self):
        """Test LLVM modification on Windows."""
        env_vars = compute_projects.get_env_variables(["llvm/CMakeLists.txt"], "Windows")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;llvm;mlir;polly",
            "check-clang check-clang-tools check-lld check-llvm check-mlir check-polly",
            "", "", ""
        )

    def test_llvm_modification_mac(self):
        """Test LLVM modification on macOS."""
        env_vars = compute_projects.get_env_variables(["llvm/CMakeLists.txt"], "Darwin")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;llvm;mlir",
            "check-clang check-clang-tools check-lld check-llvm check-mlir",
            "", "", ""
        )

    def test_clang_modification_linux(self):
        """Test Clang modification on Linux."""
        env_vars = compute_projects.get_env_variables(["clang/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;lldb;llvm",
            "check-clang check-clang-tools check-lldb",
            "compiler-rt;libcxx;libcxxabi;libunwind",
            "check-compiler-rt",
            "check-cxx check-cxxabi check-unwind",
            "OFF"
        )

    def test_clang_modification_windows(self):
        """Test Clang modification on Windows."""
        env_vars = compute_projects.get_env_variables(["clang/CMakeLists.txt"], "Windows")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;llvm",
            "check-clang check-clang-tools",
            "compiler-rt",
            "check-compiler-rt",
            "", "OFF"
        )

    def test_compiler_rt_modification(self):
        """Test compiler-rt modification."""
        env_vars = compute_projects.get_env_variables(["compiler-rt/lib/asan/asan_allocator.cpp"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;lld",
            "",
            "compiler-rt",
            "check-compiler-rt",
            "", "OFF"
        )

    def test_cir_modification(self):
        """Test CIR modification."""
        env_vars = compute_projects.get_env_variables(["clang/lib/CIR/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;lldb;llvm;mlir",
            "check-clang check-clang-cir check-clang-tools check-lldb",
            "compiler-rt;libcxx;libcxxabi;libunwind",
            "check-compiler-rt",
            "check-cxx check-cxxabi check-unwind",
            "ON"
        )

    def test_bolt_modification(self):
        """Test BOLT modification."""
        env_vars = compute_projects.get_env_variables(["bolt/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;lld;llvm",
            "check-bolt",
            "", "", "", "OFF"
        )

    def test_lldb_modification(self):
        """Test LLDB modification."""
        env_vars = compute_projects.get_env_variables(["lldb/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;lldb;llvm",
            "check-lldb",
            "libcxx;libcxxabi;libunwind",
            "", "", "OFF"
        )

    def test_mlir_modification(self):
        """Test MLIR modification."""
        env_vars = compute_projects.get_env_variables(["mlir/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;flang;llvm;mlir",
            "check-flang check-mlir",
            "", "", "", "OFF"
        )

    def test_flang_modification(self):
        """Test Flang modification."""
        env_vars = compute_projects.get_env_variables(["flang/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;flang;llvm",
            "check-flang",
            "flang-rt",
            "check-flang-rt",
            "", "OFF"
        )

    def test_invalid_subproject(self):
        """Test modification in invalid subproject."""
        env_vars = compute_projects.get_env_variables(["llvm-libgcc/CMakeLists.txt"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_top_level_file(self):
        """Test top-level file modification."""
        env_vars = compute_projects.get_env_variables(["README.md"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_exclude_libcxx_in_projects(self):
        """Test libcxx exclusion from projects."""
        env_vars = compute_projects.get_env_variables(["libcxx/CMakeLists.txt"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_include_libc_in_runtimes(self):
        """Test libc inclusion in runtimes."""
        env_vars = compute_projects.get_env_variables(["libc/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;lld",
            "",
            "libc",
            "check-libc",
            "", "OFF"
        )

    def test_exclude_docs(self):
        """Test documentation exclusion."""
        env_vars = compute_projects.get_env_variables(["llvm/docs/CIBestPractices.rst"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_exclude_gn(self):
        """Test GN build system exclusion."""
        env_vars = compute_projects.get_env_variables(["llvm/utils/gn/build/BUILD.gn"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_ci_scripts_modification(self):
        """Test CI scripts modification."""
        env_vars = compute_projects.get_env_variables([".ci/compute_projects.py"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;clang-tools-extra;flang;libclc;lld;lldb;llvm;mlir;polly",
            "check-bolt check-clang check-clang-cir check-clang-tools check-flang check-lld check-lldb check-llvm check-mlir check-polly",
            "compiler-rt;flang-rt;libc;libcxx;libcxxabi;libunwind",
            "check-compiler-rt check-flang-rt check-libc",
            "check-cxx check-cxxabi check-unwind",
            "ON"
        )

    def test_windows_ci_scripts(self):
        """Test CI scripts on Windows."""
        env_vars = compute_projects.get_env_variables([".ci/compute_projects.py"], "Windows")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;libclc;lld;llvm;mlir;polly",
            "check-clang check-clang-cir check-clang-tools check-lld check-llvm check-mlir check-polly",
            "compiler-rt",
            "check-compiler-rt",
            "", "ON"
        )

    def test_clang_tools_extra_modification(self):
        """Test clang-tools-extra modification."""
        env_vars = compute_projects.get_env_variables(["clang-tools-extra/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "clang;clang-tools-extra;lld;llvm",
            "check-clang-tools",
            "libc",
            "check-libc",
            "", "OFF"
        )

    def test_premerge_workflow_modification(self):
        """Test premerge workflow modification."""
        env_vars = compute_projects.get_env_variables([".github/workflows/premerge.yaml"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;clang-tools-extra;flang;libclc;lld;lldb;llvm;mlir;polly",
            "check-bolt check-clang check-clang-cir check-clang-tools check-flang check-lld check-lldb check-llvm check-mlir check-polly",
            "compiler-rt;flang-rt;libc;libcxx;libcxxabi;libunwind",
            "check-compiler-rt check-flang-rt check-libc",
            "check-cxx check-cxxabi check-unwind",
            "ON"
        )

    def test_other_github_workflow(self):
        """Test other GitHub workflow modification."""
        env_vars = compute_projects.get_env_variables([".github/workflows/docs.yml"], "Linux")
        self._assert_env_variables(env_vars, "", "", "", "", "", "OFF")

    def test_third_party_benchmark(self):
        """Test third-party benchmark modification."""
        env_vars = compute_projects.get_env_variables(["third-party/benchmark/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;clang-tools-extra;flang;libclc;lld;lldb;llvm;mlir;polly",
            "check-bolt check-clang check-clang-cir check-clang-tools check-flang check-lld check-lldb check-llvm check-mlir check-polly",
            "compiler-rt;flang-rt;libc;libcxx;libcxxabi;libunwind",
            "check-compiler-rt check-flang-rt check-libc",
            "check-cxx check-cxxabi check-unwind",
            "ON"
        )

    def test_lit_modification(self):
        """Test lit modification."""
        env_vars = compute_projects.get_env_variables(["llvm/utils/lit/CMakeLists.txt"], "Linux")
        self._assert_env_variables(
            env_vars,
            "bolt;clang;clang-tools-extra;flang;lld;lldb;llvm;mlir;polly",
            "check-bolt check-clang check-clang-tools check-flang check-lit check-lld check-lldb check-llvm check-mlir check-polly",
            "libcxx;libcxxabi;libunwind",
            "",
            "check-cxx check-cxxabi check-unwind",
            "OFF"
        )


if __name__ == "__main__":
    unittest.main()
