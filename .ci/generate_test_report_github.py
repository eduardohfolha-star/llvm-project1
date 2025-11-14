"""Script to generate a build report for Github."""

import argparse
import generate_test_report_lib


def main():
    parser = argparse.ArgumentParser(
        description="Generate test report for GitHub from build results"
    )
    parser.add_argument("return_code", type=int, help="The build's return code")
    parser.add_argument(
        "build_test_logs", 
        nargs="*", 
        help="Paths to JUnit report files and ninja logs"
    )
    
    args = parser.parse_args()

    report = generate_test_report_lib.generate_report_from_files(
        generate_test_report_lib.compute_platform_title(),
        args.return_code,
        args.build_test_logs,
    )

    print(report)


if __name__ == "__main__":
    main()
