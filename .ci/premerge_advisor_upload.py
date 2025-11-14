"""Script for uploading results to the premerge advisor."""

import argparse
import os
import platform
import sys

import requests

import generate_test_report_lib

PREMERGE_ADVISOR_URLS = [
    "http://34.82.126.63:5000/upload",
    "http://136.114.125.23:5000/upload",
]


class FailureDataPreparer:
    """Prepara dados de falha para upload."""
    
    def __init__(self):
        self.report_generator = generate_test_report_lib.TestReportGenerator()

    def prepare_upload_data(self, commit_sha: str, workflow_run_number: str, 
                          build_log_files: list[str]) -> dict:
        """Prepara dados para upload para o premerge advisor."""
        junit_objects, ninja_logs = generate_test_report_lib.load_info_from_files(build_log_files)
        
        source_type = "pull_request" if "GITHUB_ACTIONS" in os.environ else "postcommit"
        current_platform = f"{platform.system()}-{platform.machine()}".lower()
        
        upload_data = {
            "source_type": source_type,
            "base_commit_sha": commit_sha,
            "source_id": workflow_run_number,
            "failures": [],
            "platform": current_platform,
        }

        # Coleta falhas de testes
        test_failures = self.report_generator.get_test_failures(junit_objects)
        for suite_failures in test_failures.values():
            for test_name, failure_message in suite_failures:
                upload_data["failures"].append({
                    "name": test_name,
                    "message": failure_message
                })

        # Coleta falhas de build se não houver falhas de teste
        if not upload_data["failures"]:
            ninja_failures = self.report_generator.find_failures_in_ninja_logs(ninja_logs)
            for action_name, failure_message in ninja_failures:
                upload_data["failures"].append({
                    "name": action_name,
                    "message": failure_message
                })
                
        return upload_data


class PremergeAdvisorUploader:
    """Faz upload de dados para instâncias do premerge advisor."""
    
    def __init__(self, urls: list[str] = None):
        self.urls = urls or PREMERGE_ADVISOR_URLS
        self.data_preparer = FailureDataPreparer()

    def upload_to_all_instances(self, commit_sha: str, workflow_run_number: str,
                              build_log_files: list[str]):
        """Faz upload para todas as instâncias do premerge advisor."""
        upload_data = self.data_preparer.prepare_upload_data(
            commit_sha, workflow_run_number, build_log_files
        )
        
        for url in self.urls:
            try:
                response = requests.post(url, json=upload_data, timeout=5)
                response.raise_for_status()
                print(f"Successfully uploaded to {url}")
            except requests.RequestException as error:
                print(f"Failed to upload to {url}: {error}")


def main(commit_sha: str, workflow_run_number: str, build_log_files: list[str]):
    """Função principal de upload."""
    # Skip em ARM64 temporariamente
    if platform.machine() == "arm64":
        print("Skipping upload on ARM64")
        return

    uploader = PremergeAdvisorUploader()
    uploader.upload_to_all_instances(commit_sha, workflow_run_number, build_log_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload test results to premerge advisor"
    )
    parser.add_argument("commit_sha", help="The base commit SHA for the test.")
    parser.add_argument("workflow_run_number", help="The run number from GHA.")
    parser.add_argument(
        "build_log_files", 
        nargs="*", 
        help="Paths to JUnit report files and ninja logs."
    )
    
    args = parser.parse_args()

    main(args.commit_sha, args.workflow_run_number, args.build_log_files)
