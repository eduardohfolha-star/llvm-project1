"""Tests for generate_test_report_lib.py"""

import unittest
from io import StringIO
from textwrap import dedent
import tempfile
import os

from junitparser import JUnitXml
import generate_test_report_lib


def junit_from_xml(xml_content: str):
    """Cria objeto JUnit a partir de string XML."""
    return JUnitXml.fromfile(StringIO(xml_content))


class TestReportGeneration(unittest.TestCase):
    """Test cases for test report generation."""
    
    def setUp(self):
        """Configura o generator para cada teste."""
        self.generator = generate_test_report_lib.TestReportGenerator()

    def test_ninja_log_failure_parsing(self):
        """Test parsing failures from ninja logs."""
        failures = self.generator.find_failures_in_ninja_logs([
            [
                "[1/5] test/1.stamp",
                "[2/5] test/2.stamp", 
                "[3/5] test/3.stamp",
                "[4/5] test/4.stamp",
                "FAILED: touch test/4.stamp",
                "Wow! This system is really broken!",
                "[5/5] test/5.stamp",
            ],
        ])
        
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            failures[0],
            (
                "touch test/4.stamp",
                dedent("""\
                    FAILED: touch test/4.stamp
                    Wow! This system is really broken!"""),
            ),
        )

    def test_ninja_log_no_failures(self):
        """Test ninja log without failures."""
        failures = self.generator.find_failures_in_ninja_logs([
            [
                "[1/3] test/1.stamp",
                "[2/3] test/2.stamp", 
                "[3/3] test/3.stamp",
            ]
        ])
        self.assertEqual(failures, [])

    def test_ninja_log_multiple_failures(self):
        """Test ninja log with multiple failures."""
        failures = self.generator.find_failures_in_ninja_logs([
            [
                "[1/5] test/1.stamp",
                "[2/5] test/2.stamp",
                "FAILED: touch test/2.stamp",
                "First failure!",
                "[3/5] test/3.stamp",
                "[4/5] test/4.stamp", 
                "FAILED: touch test/4.stamp",
                "Second failure!",
                "[5/5] test/5.stamp",
            ]
        ])
        
        self.assertEqual(len(failures), 2)
        self.assertEqual(failures[0][0], "touch test/2.stamp")
        self.assertEqual(failures[1][0], "touch test/4.stamp")

    def test_report_title_only_success(self):
        """Test report with only title and successful build."""
        report = self.generator.generate_report("Foo", 0, [], [])
        expected = dedent("""\
            # Foo

            The build succeeded and no tests ran. This is expected in some build configurations.""")
        self.assertEqual(report, expected)

    def test_report_title_only_failure(self):
        """Test report with only title and failed build."""
        report = self.generator.generate_report("Foo", 1, [], [])
        self.assertIn("The build failed before running any tests", report)
        self.assertIn("Download the build's log file", report)

    def test_report_with_passing_tests(self):
        """Test report with passing tests."""
        report = self.generator.generate_report(
            "Test Suite",
            0,
            [
                junit_from_xml(dedent("""\
                    <?xml version="1.0" encoding="UTF-8"?>
                    <testsuites time="1.0">
                    <testsuite name="Suite1" tests="2" failures="0" skipped="0" time="1.0">
                    <testcase classname="Class1" name="test1" time="0.5"/>
                    <testcase classname="Class1" name="test2" time="0.5"/>
                    </testsuite>
                    </testsuites>"""))
            ],
            [],
        )
        
        self.assertIn("* 2 tests passed", report)
        self.assertNotIn("failed", report)

    def test_report_with_test_failures(self):
        """Test report with test failures."""
        report = self.generator.generate_report(
            "Foo",
            1,
            [
                junit_from_xml(dedent("""\
                    <?xml version="1.0" encoding="UTF-8"?>
                    <testsuites time="8.89">
                    <testsuite name="Bar" tests="4" failures="2" skipped="1" time="410.63">
                    <testcase classname="Bar/test_1" name="test_1" time="0.02"/>
                    <testcase classname="Bar/test_2" name="test_2" time="0.02">
                      <skipped message="Reason"/>
                    </testcase>
                    <testcase classname="Bar/test_3" name="test_3" time="0.02">
                      <failure><![CDATA[Output goes here]]></failure>
                    </testcase>
                    <testcase classname="Bar/test_4" name="test_4" time="0.02">
                      <failure><![CDATA[Other output goes here]]></failure>
                    </testcase>
                    </testsuite>
                    </testsuites>"""))
            ],
            [],
        )
        
        self.assertIn("* 1 test passed", report)
        self.assertIn("* 1 test skipped", report) 
        self.assertIn("* 2 tests failed", report)
        self.assertIn("Bar/test_3", report)
        self.assertIn("Bar/test_4", report)

    def test_report_size_limiting(self):
        """Test report size limiting."""
        large_output = "x" * 5000
        report = self.generator.generate_report(
            "Foo",
            1,
            [
                junit_from_xml(dedent(f"""\
                    <?xml version="1.0" encoding="UTF-8"?>
                    <testsuites time="0.02">
                    <testsuite name="Bar" tests="1" failures="1" skipped="0" time="0.02">
                    <testcase classname="Bar/test_1" name="test_1" time="0.02">
                      <failure><![CDATA[{large_output}]]></failure>
                    </testcase>
                    </testsuite>
                    </testsuites>"""))
            ],
            [],
            size_limit=512,
        )
        
        self.assertIn("too large to report", report)

    def test_report_with_failure_explanations(self):
        """Test report with failure explanations from advisor."""
        report = self.generator.generate_report(
            "Foo",
            1,
            [
                junit_from_xml(dedent("""\
                    <?xml version="1.0" encoding="UTF-8"?>
                    <testsuites time="0.02">
                    <testsuite name="Bar" tests="1" failures="1" skipped="0" time="0.02">
                    <testcase classname="Bar/test_1" name="test_1" time="0.02">
                      <failure><![CDATA[Test failure message]]></failure>
                    </testcase>
                    </testsuite>
                    </testsuites>"""))
            ],
            [],
            failure_explanations=[
                {
                    "name": "Bar/test_1/test_1",
                    "explained": True,
                    "reason": "This is a known issue"
                }
            ]
        )
        
        self.assertIn("(Likely Already Failing)", report)
        self.assertIn("This is a known issue", report)

    def test_end_to_end_report_generation(self):
        """Test end-to-end report generation from files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            junit_file = os.path.join(temp_dir, "test.xml")
            with open(junit_file, "w", encoding="utf-8") as f:
                f.write(dedent("""\
                    <?xml version="1.0" encoding="UTF-8"?>
                    <testsuites time="0.00">
                    <testsuite name="Passed" tests="1" failures="0" skipped="0" time="0.00">
                    <testcase classname="Bar/test_1" name="test_1" time="0.00"/>
                    </testsuite>
                    </testsuites>"""))
                    
            ninja_file = os.path.join(temp_dir, "build.log")  
            with open(ninja_file, "w", encoding="utf-8") as f:
                f.write(dedent("""\
                    [1/5] test/1.stamp
                    [2/5] test/2.stamp
                    [3/5] test/3.stamp
                    [4/5] test/4.stamp
                    FAILED: test/4.stamp
                    touch test/4.stamp
                    Build failed!
                    [5/5] test/5.stamp"""))
                    
            report = generate_test_report_lib.generate_report_from_files(
                "Test", 1, [junit_file, ninja_file]
            )
            
            self.assertIn("# Test", report)
            self.assertIn("test/4.stamp", report)

    def test_get_test_failures_from_junit(self):
        """Test extracting failures from JUnit objects."""
        junit_objects = [
            junit_from_xml(dedent("""\
                <?xml version="1.0" encoding="UTF-8"?>
                <testsuites>
                <testsuite name="Suite1" tests="2" failures="1">
                <testcase classname="Class1" name="test1" time="0.1">
                  <failure>Failure message</failure>
                </testcase>
                <testcase classname="Class1" name="test2" time="0.1"/>
                </testsuite>
                </testsuites>"""))
        ]
        
        failures = self.generator.get_test_failures(junit_objects)
        self.assertIn("Suite1", failures)
        self.assertEqual(len(failures["Suite1"]), 1)
        self.assertEqual(failures["Suite1"][0][0], "Class1/test1")


if __name__ == "__main__":
    unittest.main()
