from mock import patch
import unittest
import json

from tests.factories.model.project import ProjectFactory
from tests.factories.model.application import ApplicationFactory
from tests.factories.model.package import PackageFactory
from tds.views import cli


class TestFormatSetting(unittest.TestCase):

    def test_format(self):
        CLI = cli.CLI("blocks")
        self.assertEqual(CLI.output_format, "blocks")

class TestApplicationOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.apps = [ApplicationFactory(),
                     ApplicationFactory()]

    @patch('tds.views.cli.format_application')
    def test_generate_application_list_result(self, format_application):
        cli.CLI("blocks").generate_application_list_result(result=self.apps)
        format_application.assert_called_with(self.apps, "blocks")

    def test_single_app_blocks_format(self):
        output = cli.format_application(self.apps[0])
        expected = cli.APPLICATION_TEMPLATE.format(self=self.apps[0])
        self.assertEqual(output, expected)

    def test_mult_app_blocks_format(self):
        output = cli.format_application(self.apps)
        expected = "\n\n{block}\n\n{block}".format(
            block=cli.APPLICATION_TEMPLATE.format(self=self.apps[0]),
        )
        self.assertEqual(output, expected)

    @patch('tagopsdb.PackageDefinition.to_dict')
    def test_single_app_json_format(self, to_dict):
        to_dict.return_value = vars(self.apps[0])
        output = json.loads(cli.format_application(self.apps[0], "json"))
        expected = vars(self.apps[0])
        self.assertEqual(output, expected)

    @patch('tagopsdb.PackageDefinition.to_dict')
    def test_mult_app_json_format(self, to_dict):
        to_dict.return_value = vars(self.apps[0])
        output = json.loads(cli.format_application(self.apps, "json"))
        expected = [vars(self.apps[0]), vars(self.apps[0])]
        self.assertEqual(output, expected)

    def test_single_app_table_format(self):
        output = cli.format_application(self.apps[0], "table")
        expected = "| Application   |\n|---------------|\n| fake_package  |"
        self.assertEqual(output, expected)

    def test_mult_app_table_format(self):
        output = cli.format_application(self.apps, "table")
        expected = "| Application   |\n|---------------|\n| fake_package  | fake_package  |"


class TestPackageOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.packages = [PackageFactory(),
                         PackageFactory()]

    @patch('tds.views.cli.format_package')
    def test_generate_package_list_result(self, format_package):
        cli.CLI("blocks").generate_package_list_result(result=self.packages)
        format_package.assert_called_with(self.packages, "blocks")

    def test_single_pkg_blocks_format(self):
        output = cli.format_package(self.packages[0])
        expected = cli.PACKAGE_TEMPLATE.format(self=self.packages[0])
        self.assertEqual(output, expected)

    def test_mult_pkg_blocks_format(self):
        output = cli.format_package(self.packages)
        expected = "\n\n{block1}\n\n{block2}".format(
            block1=cli.PACKAGE_TEMPLATE.format(self=self.packages[0]),
            block2=cli.PACKAGE_TEMPLATE.format(self=self.packages[1])
        )
        self.assertEqual(output, expected)

    # TODO: Get these tests to work
    # @patch('tagopsdb.Package.to_dict')
    # def test_single_pkg_json_format(self, to_dict):
    #     to_dict.return_value = vars(self.packages[0])
    #     output = json.loads(cli.format_package(self.packages[0], "json"))
    #     expected = vars(self.packages[0])
    #     self.assertEqual(output, expected)
    #
    # @patch('tagopsdb.Package.to_dict')
    # def test_mult_pkg_json_format(self, to_dict):
    #     to_dict.return_value = [vars(self.packages[0]), vars(self.packages[1])]
    #     output = json.loads(cli.format_package(self.packages, "json"))
    #     expected = [vars(self.packages[0]), vars(self.packages[1])]
    #     self.assertEqual(output, expected)

    def test_single_pkg_table_format(self):
        output = cli.format_package(self.packages[0], "table")
        expected = "| Project      | Version   | Revision   |\n|--------------+-----------+------------|\n| fake_package | badf00d   | tums       |"
        self.assertEqual(output, expected)

    def test_mult_pkg_table_format(self):
        output = cli.format_package(self.packages, "table")
        expected = "| Project      | Version   | Revision   |\n|--------------+-----------+------------|\n| fake_package | badf00d   | tums       |\n| fake_package | badf00d   | tums       |"
        self.assertEqual(output, expected)


class TestProjectOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.projects = [ProjectFactory(name="proj1"),
                         ProjectFactory(name="proj2")]

    @patch('tds.views.cli.format_project')
    def test_generate_project_list_result(self, format_project):
        cli.CLI("blocks").generate_project_list_result(result=self.projects)
        format_project.assert_called_with(self.projects, "blocks")

# TODO: Write this test suite more fully
#
#     def test_single_proj_blocks_format(self):
#         output = cli.format_project(self.projects[0])
#         assert False, output
