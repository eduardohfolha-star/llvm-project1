"""Script for getting explanations from the premerge advisor."""

import argparse
import json
import platform
import sys
from typing import Optional

import requests
import github
import github.PullRequest

import generate_test_report_lib

PREMERGE_ADVISOR_URL = (
    "http://premerge-advisor.premerge-advisor.svc.cluster.local:5000/explain"
)
COMMENT_TAG = "<!--PREMERGE ADVISOR COMMENT: {platform}-->"


class GitHubCommentManager:
    """Gerencia comentários no GitHub para o premerge advisor."""
    
    def __init__(self, github_token: str, pr_number: int):
        self.github = github.Github(github_token)
        self.repo = self.github.get_repo("llvm/llvm-project")
        self.pr = self.repo.get_issue(pr_number).as_pull_request()

    def get_existing_comment_id(self, platform_name: str) -> Optional[int]:
        """Obtém o ID de um comentário existente para a plataforma."""
        platform_tag = COMMENT_TAG.format(platform=platform_name)
        
        for comment in self.pr.as_issue().get_comments():
            if platform_tag in comment.body:
                return comment.id
        return None

    def prepare_comment_data(self, body: str, platform_name: str) -> dict:
        """Prepara dados do comentário para a API do GitHub."""
        comment = {"body": body}
        comment_id = self.get_existing_comment_id(platform_name)
        
        if comment_id:
            comment["id"] = comment_id
            
        return comment


class PremergeAdvisorClient:
    """Cliente para o serviço Premerge Advisor."""
    
    def __init__(self, base_url: str = PREMERGE_ADVISOR_URL):
        self.base_url = base_url

    def get_failure_explanations(self, commit_sha: str, platform_name: str, 
                               failures: list[dict]) -> Optional[list]:
        """Obtém explicações para falhas do premerge advisor."""
        request_data = {
            "base_commit_sha": commit_sha,
            "platform": platform_name,
            "failures": failures,
        }
        
        try:
            response = requests.get(self.base_url, json=request_data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            print(f"Error contacting premerge advisor: {error}")
            return None


class FailureCollector:
    """Coleta falhas de testes e builds."""
    
    def __init__(self):
        self.report_generator = generate_test_report_lib.TestReportGenerator()

    def collect_failures(self, build_log_files: list[str]) -> list[dict]:
        """Coleta todas as falhas de testes e builds."""
        junit_objects, ninja_logs = generate_test_report_lib.load_info_from_files(build_log_files)
        failures = []
        
        # Coleta falhas de testes
        test_failures = self.report_generator.get_test_failures(junit_objects)
        for suite_failures in test_failures.values():
            for test_name, failure_message in suite_failures:
                failures.append({
                    "name": test_name,
                    "message": failure_message
                })
        
        # Se não há falhas de testes, coleta falhas de build
        if not failures:
            ninja_failures = self.report_generator.find_failures_in_ninja_logs(ninja_logs)
            for action_name, failure_message in ninja_failures:
                failures.append({
                    "name": action_name, 
                    "message": failure_message
                })
                
        return failures


def main(commit_sha: str, build_log_files: list[str], github_token: str,
         pr_number: int, return_code: int):
    """Função principal do script."""
    
    # Skip em ARM64 temporariamente
    if platform.machine() == "arm64":
        print("Skipping premerge advisor on ARM64")
        return

    current_platform = f"{platform.system()}-{platform.machine()}".lower()
    comment_manager = GitHubCommentManager(github_token, pr_number)
    
    if return_code == 0:
        # Build bem-sucedido - atualiza comentário existente
        comment_body = (
            ":white_check_mark: With the latest revision this PR passed "
            "the premerge checks."
        )
        comment_data = comment_manager.prepare_comment_data(comment_body, current_platform)
        
        with open("comment", "w", encoding="utf-8") as comment_file:
            json.dump([comment_data], comment_file)
        return

    # Build falhou - processa falhas
    failure_collector = FailureCollector()
    advisor_client = PremergeAdvisorClient()
    
    failures = failure_collector.collect_failures(build_log_files)
    explanations = advisor_client.get_failure_explanations(commit_sha, current_platform, failures)
    
    # Gera relatório com explicações
    junit_objects, ninja_logs = generate_test_report_lib.load_info_from_files(build_log_files)
    report = generate_test_report_lib.generate_report(
        generate_test_report_lib.compute_platform_title(),
        return_code,
        junit_objects,
        ninja_logs,
        failure_explanations_list=explanations or []
    )
    
    comment_data = comment_manager.prepare_comment_data(report, current_platform)
    
    with open("comment", "w", encoding="utf-8") as comment_file:
        json.dump([comment_data], comment_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Get explanations from premerge advisor and update GitHub comments"
    )
    parser.add_argument("commit_sha", help="The base commit SHA for the test.")
    parser.add_argument("return_code", type=int, help="The build's return code")
    parser.add_argument("github_token", help="GitHub authentication token")
    parser.add_argument("pr_number", type=int, help="The PR number")
    parser.add_argument(
        "build_log_files", 
        nargs="*", 
        help="Paths to JUnit report files and ninja logs."
    )
    
    args = parser.parse_args()

    main(
        args.commit_sha,
        args.build_log_files,
        args.github_token,
        args.pr_number,
        args.return_code,
    )
