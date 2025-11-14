"""Library to parse JUnit XML files and generate markdown reports."""

from typing import TypedDict, Optional
import platform

from junitparser import JUnitXml, Failure


class FailureExplanation(TypedDict):
    """Estrutura para explicações de falhas do advisor."""
    name: str
    explained: bool
    reason: Optional[str]


# Constantes para mensagens
SEE_BUILD_FILE_STR = "Download the build's log file to see the details."
UNRELATED_FAILURES_STR = (
    "If these failures are unrelated to your changes (for example "
    "tests are broken or flaky at HEAD), please open an issue at "
    "https://github.com/llvm/llvm-project/issues and add the "
    "`infrastructure` label."
)
NINJA_LOG_SIZE_THRESHOLD = 500


class TestReportGenerator:
    """Gera relatórios de teste a partir de arquivos de log e JUnit."""
    
    def __init__(self):
        self.failure_explanations = {}

    def _parse_ninja_log(self, ninja_log: list[str]) -> list[tuple[str, str]]:
        """Analisa um log do ninja em busca de falhas."""
        failures = []
        index = 0
        
        while index < len(ninja_log):
            # Encontra a próxima falha
            while index < len(ninja_log) and not ninja_log[index].startswith("FAILED:"):
                index += 1
                
            if index >= len(ninja_log):
                break
                
            # Ignora falhas de sub-ninja
            if index > 0 and ninja_log[index - 1].startswith("ninja: build stopped:"):
                index += 1
                continue
                
            failing_action = ninja_log[index].split("FAILED: ")[1]
            failure_log = []
            
            # Coleta linhas da falha
            while (index < len(ninja_log) and 
                   not ninja_log[index].startswith("[") and
                   not ninja_log[index].startswith("ninja: build stopped:") and
                   len(failure_log) < NINJA_LOG_SIZE_THRESHOLD):
                failure_log.append(ninja_log[index])
                index += 1
                
            failures.append((failing_action, "\n".join(failure_log)))
            
        return failures

    def find_failures_in_ninja_logs(self, ninja_logs: list[list[str]]) -> list[tuple[str, str]]:
        """Extrai mensagens de falha de logs do ninja."""
        all_failures = []
        for ninja_log in ninja_logs:
            all_failures.extend(self._parse_ninja_log(ninja_log))
        return all_failures

    def _format_failure_details(self, failure: tuple[str, str]) -> list[str]:
        """Formata os detalhes de uma falha para o relatório."""
        failed_action, failure_message = failure
        explanation = self.failure_explanations.get(failed_action)
        
        output = ["<details>"]
        
        if explanation and explanation["explained"]:
            output.extend([
                f"<summary>{failed_action} (Likely Already Failing)</summary>",
                "",
                explanation["reason"],
                "",
            ])
        else:
            output.append(f"<summary>{failed_action}</summary>")
            output.append("")
            
        output.extend([
            "```",
            failure_message,
            "```",
            "</details>",
        ])
        
        return output

    def get_test_failures(self, junit_objects) -> dict[str, list[tuple[str, str]]]:
        """Extrai falhas de testes dos objetos JUnit."""
        failures = {}
        
        for test_suite in junit_objects:
            for test_case in test_suite:
                if (not test_case.is_passed and test_case.result and 
                    isinstance(test_case.result[0], Failure)):
                    
                    suite_name = test_suite.name
                    if suite_name not in failures:
                        failures[suite_name] = []
                        
                    test_id = f"{test_case.classname}/{test_case.name}"
                    failure_text = test_case.result[0].text
                    failures[suite_name].append((test_id, failure_text))
                    
        return failures

    def _generate_summary_section(self, tests_run: int, tests_skipped: int, 
                                tests_failed: int) -> list[str]:
        """Gera a seção de resumo do relatório."""
        summary = []
        tests_passed = tests_run - tests_skipped - tests_failed
        
        def plural(count: int) -> str:
            return "test" if count == 1 else "tests"
            
        if tests_passed:
            summary.append(f"* {tests_passed} {plural(tests_passed)} passed")
        if tests_skipped:
            summary.append(f"* {tests_skipped} {plural(tests_skipped)} skipped")
        if tests_failed:
            summary.append(f"* {tests_failed} {plural(tests_failed)} failed")
            
        return summary

    def _generate_failures_section(self, failures: dict[str, list[tuple[str, str]]]) -> list[str]:
        """Gera a seção de falhas do relatório."""
        if not failures:
            return []
            
        section = ["", "## Failed Tests", "(click on a test name to see its output)"]
        
        for suite_name, suite_failures in failures.items():
            section.extend(["", f"### {suite_name}"])
            for failure in suite_failures:
                section.extend(self._format_failure_details(failure))
                
        return section

    def _generate_ninja_failures_section(self, ninja_failures: list[tuple[str, str]]) -> list[str]:
        """Gera seção para falhas de build do ninja."""
        if not ninja_failures:
            return []
            
        section = [
            "",
            "The build failed before running any tests. Click on a failure below to see the details.",
            "",
        ]
        
        for failure in ninja_failures:
            section.extend(self._format_failure_details(failure))
            
        return section

    def generate_report(self, title: str, return_code: int, junit_objects, 
                       ninja_logs: list[list[str]], size_limit: int = 1024 * 1024,
                       list_failures: bool = True, 
                       failure_explanations: list[FailureExplanation] = None) -> str:
        """Gera relatório completo de testes."""
        if failure_explanations is None:
            failure_explanations = []
            
        # Prepara explicações de falhas
        self.failure_explanations = {
            exp["name"]: exp for exp in failure_explanations if exp["explained"]
        }
        
        # Coleta estatísticas de teste
        tests_run = tests_skipped = tests_failed = 0
        for test_suite in junit_objects:
            tests_run += test_suite.tests
            tests_skipped += test_suite.skipped
            tests_failed += test_suite.failures
            
        # Constrói relatório
        report = [f"# {title}", ""]
        
        if tests_run == 0:
            if return_code == 0:
                report.append(
                    "The build succeeded and no tests ran. This is expected in some build configurations."
                )
            else:
                ninja_failures = self.find_failures_in_ninja_logs(ninja_logs)
                if not ninja_failures:
                    report.extend([
                        "The build failed before running any tests. Detailed "
                        "information about the build failure could not be automatically obtained.",
                        "",
                        SEE_BUILD_FILE_STR,
                        "",
                        UNRELATED_FAILURES_STR,
                    ])
                else:
                    report.extend(self._generate_ninja_failures_section(ninja_failures))
                    report.extend(["", UNRELATED_FAILURES_STR])
                    
            return "\n".join(report)
            
        # Adiciona resumo
        report.extend(self._generate_summary_section(tests_run, tests_skipped, tests_failed))
        
        # Adiciona falhas se permitido
        test_failures = self.get_test_failures(junit_objects)
        
        if not list_failures:
            report.extend([
                "",
                "Failed tests and their output was too large to report. " + SEE_BUILD_FILE_STR,
            ])
        elif test_failures:
            report.extend(self._generate_failures_section(test_failures))
        elif return_code != 0:
            # Build falhou mas todos os testes passaram
            ninja_failures = self.find_failures_in_ninja_logs(ninja_logs)
            if not ninja_failures:
                report.extend([
                    "",
                    "All tests passed but another part of the build **failed**. "
                    "Information about the build failure could not be automatically obtained.",
                    "",
                    SEE_BUILD_FILE_STR,
                ])
            else:
                report.extend([
                    "",
                    "All tests passed but another part of the build **failed**. "
                    "Click on a failure below to see the details.",
                    "",
                ])
                report.extend(self._generate_ninja_failures_section(ninja_failures))
                
        if test_failures or return_code != 0:
            report.extend(["", UNRELATED_FAILURES_STR])
            
        # Verifica limite de tamanho
        report_str = "\n".join(report)
        if len(report_str.encode("utf-8")) > size_limit and list_failures:
            return self.generate_report(
                title, return_code, junit_objects, ninja_logs, 
                size_limit, list_failures=False
            )
            
        return report_str


def load_info_from_files(build_log_files: list[str]):
    """Carrega informações de testes a partir de arquivos."""
    junit_files = [f for f in build_log_files if f.endswith(".xml")]
    ninja_log_files = [f for f in build_log_files if f.endswith(".log")]
    
    junit_objects = [JUnitXml.fromfile(path) for path in junit_files]
    
    ninja_logs = []
    for log_file in ninja_log_files:
        with open(log_file, "r", encoding="utf-8") as file:
            ninja_logs.append([line.strip() for line in file.readlines()])
            
    return junit_objects, ninja_logs


def generate_report_from_files(title: str, return_code: int, build_log_files: list[str]) -> str:
    """Gera relatório a partir de arquivos de log."""
    junit_objects, ninja_logs = load_info_from_files(build_log_files)
    generator = TestReportGenerator()
    return generator.generate_report(title, return_code, junit_objects, ninja_logs)


def compute_platform_title() -> str:
    """Calcula o título da plataforma para o relatório."""
    logo = ":window:" if platform.system() == "Windows" else ":penguin:"
    
    if platform.machine() in ("x86_64", "AMD64"):
        arch = "x64"
    else:
        arch = platform.machine()
        
    return f"{logo} {platform.system()} {arch} Test Results"
