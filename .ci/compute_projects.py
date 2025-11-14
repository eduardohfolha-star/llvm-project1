"""Compute the list of projects that need testing based on diff changes."""

from collections.abc import Set
import pathlib
import platform
import sys

# ... (constantes mantidas igual)

class ProjectConfiguration:
    """Gerencia a configuração de projetos e suas dependências."""
    
    def __init__(self):
        self.dependencies = PROJECT_DEPENDENCIES
        self.dependents = DEPENDENTS_TO_TEST
        self.runtime_deps = DEPENDENT_RUNTIMES_TO_BUILD
        self.test_runtimes = DEPENDENT_RUNTIMES_TO_TEST
        self.test_runtimes_reconfig = DEPENDENT_RUNTIMES_TO_TEST_NEEDS_RECONFIG
        self.check_targets = PROJECT_CHECK_TARGETS
        self.exclusions = {
            'Linux': EXCLUDE_LINUX,
            'Windows': EXCLUDE_WINDOWS, 
            'Darwin': EXCLUDE_MAC
        }

    def _add_dependencies(self, projects: Set[str], runtimes: Set[str]) -> Set[str]:
        """Adiciona dependências transitivas aos projetos."""
        projects_with_deps = set(projects)
        current_count = 0
        
        while current_count != len(projects_with_deps):
            current_count = len(projects_with_deps)
            for project in list(projects_with_deps):
                if project in self.dependencies:
                    projects_with_deps.update(self.dependencies[project])
        
        for runtime in runtimes:
            if runtime in self.dependencies:
                projects_with_deps.update(self.dependencies[runtime])
                
        return projects_with_deps

    def _exclude_platform_projects(self, projects: Set[str], platform_name: str) -> Set[str]:
        """Remove projetos excluídos para a plataforma específica."""
        return projects - self.exclusions.get(platform_name, set())

    def _compute_projects_to_test(self, modified_projects: Set[str], platform_name: str) -> Set[str]:
        """Calcula quais projetos devem ser testados."""
        projects_to_test = set()
        
        for project in modified_projects:
            if project in RUNTIMES:
                continue
                
            if project in self.check_targets:
                projects_to_test.add(project)
                
            if project in self.dependents:
                dependents = self.dependents[project]
                if platform_name == "Windows":
                    dependents = dependents - EXCLUDE_DEPENDENTS_WINDOWS
                projects_to_test.update(dependents)
        
        return self._exclude_platform_projects(projects_to_test, platform_name)

    def _compute_runtimes_to_test(self, modified_projects: Set[str], platform_name: str) -> Set[str]:
        """Calcula quais runtimes devem ser testados."""
        runtimes_to_test = set()
        
        for project in modified_projects:
            if project in self.test_runtimes:
                runtimes_to_test.update(self.test_runtimes[project])
                
        return self._exclude_platform_projects(runtimes_to_test, platform_name)

    def _compute_runtimes_to_test_needs_reconfig(self, modified_projects: Set[str], platform_name: str) -> Set[str]:
        """Calcula runtimes que precisam de reconfiguração para teste."""
        runtimes_to_test = set()
        
        for project in modified_projects:
            if project in self.test_runtimes_reconfig:
                runtimes_to_test.update(self.test_runtimes_reconfig[project])
                
        return self._exclude_platform_projects(runtimes_to_test, platform_name)

    def _compute_runtimes_to_build(self, runtimes_to_test: Set[str], modified_projects: Set[str], platform_name: str) -> Set[str]:
        """Calcula quais runtimes devem ser construídos."""
        runtimes_to_build = set(runtimes_to_test)
        
        for project in modified_projects:
            if project in self.runtime_deps:
                runtimes_to_build.update(self.runtime_deps[project])
                
        return self._exclude_platform_projects(runtimes_to_build, platform_name)

    def _get_modified_projects_for_file(self, modified_file: str) -> Set[str]:
        """Obtém projetos modificados a partir de um arquivo."""
        modified_projects = set()
        path_parts = pathlib.Path(modified_file).parts
        
        for meta_path, meta_project in META_PROJECTS.items():
            if self._path_matches(meta_path, path_parts):
                if meta_project in SKIP_PROJECTS:
                    return set()
                modified_projects.add(meta_project)
                
        modified_projects.add(path_parts[0])
        return modified_projects

    def _path_matches(self, matcher: tuple, file_path: tuple) -> bool:
        """Verifica se caminho do arquivo corresponde ao padrão."""
        if len(file_path) < len(matcher):
            return False
            
        for match_part, file_part in zip(matcher, file_path):
            if match_part in ("*", file_part):
                continue
            if match_part != file_part:
                return False
        return True

    def get_modified_projects(self, modified_files: list[str]) -> Set[str]:
        """Obtém todos os projetos modificados a partir da lista de arquivos."""
        modified_projects = set()
        
        for modified_file in modified_files:
            modified_projects.update(self._get_modified_projects_for_file(modified_file))
            
        return modified_projects

    def get_env_variables(self, modified_files: list[str], platform_name: str) -> dict:
        """Calcula todas as variáveis de ambiente necessárias."""
        modified_projects = self.get_modified_projects(modified_files)
        
        projects_to_test = self._compute_projects_to_test(modified_projects, platform_name)
        runtimes_to_test = self._compute_runtimes_to_test(modified_projects, platform_name)
        runtimes_to_test_reconfig = self._compute_runtimes_to_test_needs_reconfig(modified_projects, platform_name)
        
        runtimes_to_build = self._compute_runtimes_to_build(
            runtimes_to_test | runtimes_to_test_reconfig, modified_projects, platform_name
        )
        
        projects_to_build = self._add_dependencies(projects_to_test, runtimes_to_build)
        
        # Remove projetos que não precisam de build explícito
        for project in SKIP_BUILD_PROJECTS:
            projects_to_build.discard(project)

        return {
            'projects_to_build': ';'.join(sorted(projects_to_build)),
            'project_check_targets': ' '.join(
                sorted(self.check_targets[p] for p in projects_to_test if p in self.check_targets)
            ),
            'runtimes_to_build': ';'.join(sorted(runtimes_to_build)),
            'runtimes_check_targets': ' '.join(
                sorted(self.check_targets[r] for r in runtimes_to_test if r in self.check_targets)
            ),
            'runtimes_check_targets_needs_reconfig': ' '.join(
                sorted(self.check_targets[r] for r in runtimes_to_test_reconfig if r in self.check_targets)
            ),
            'enable_cir': 'ON' if 'CIR' in projects_to_build else 'OFF',
        }


def main():
    current_platform = platform.system()
    if len(sys.argv) == 2:
        current_platform = sys.argv[1]
        
    changed_files = [line.strip() for line in sys.stdin]
    config = ProjectConfiguration()
    env_vars = config.get_env_variables(changed_files, current_platform)
    
    for key, value in env_vars.items():
        print(f"{key}='{value}'")


if __name__ == "__main__":
    main()
