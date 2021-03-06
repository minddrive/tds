# Copyright 2016 Ifwe Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mock import patch
import unittest
import json
import sys
from StringIO import StringIO

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
        self.CLI = cli.CLI("blocks")
        sys.stdout = self.out = StringIO()

    @patch('tds.views.cli.format_application')
    def test_generate_application_list_result(self, format_application):
        self.CLI.generate_application_list_result(result=self.apps)
        format_application.assert_called_with(self.apps, "blocks")

    @patch('tds.views.cli.format_application')
    def test_generate_application_add_result(self, format_application):
        self.CLI.generate_application_add_result(result=self.apps[0])
        self.assertIn('Created {name}:'.format(name=self.apps[0].name),
                      self.out.getvalue())
        format_application.assert_called_with(self.apps[0], "blocks")

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
        expected = ("| Application   |\n|---------------|\n| fake_package  |"
                    "\n| fake_package  |")
        self.assertEqual(output, expected)


class TestPackageOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.packages = [PackageFactory(),
                         PackageFactory()]
        self.CLI = cli.CLI("blocks")
        sys.stdout = self.out = StringIO()

    @patch('tds.views.cli.format_package')
    def test_generate_package_list_result(self, format_package):
        self.CLI.generate_package_list_result(result=self.packages)
        format_package.assert_called_with(self.packages, "blocks")

    def test_generate_package_add_result(self):
        self.CLI.generate_package_add_result(
            result=dict(package=self.packages[0])
        )
        self.assertIn(
            'Added package: "{s.name}@{s.version}"'.format(
                s=self.packages[0]
            ),
            self.out.getvalue()
        )

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
    #     to_dict.return_value = [vars(self.packages[0]),
    #                             vars(self.packages[1])]
    #     output = json.loads(cli.format_package(self.packages, "json"))
    #     expected = [vars(self.packages[0]), vars(self.packages[1])]
    #     self.assertEqual(output, expected)

    def test_single_pkg_table_format(self):
        output = cli.format_package(self.packages[0], "table")
        expected = ("| Project      | Version   | Revision   |\n|"
                    "--------------+-----------+------------|\n| fake_package"
                    " | badf00d   | tums       |")
        self.assertEqual(output, expected)

    def test_mult_pkg_table_format(self):
        output = cli.format_package(self.packages, "table")
        expected = ("| Project      | Version   | Revision   |\n|"
                    "--------------+-----------+------------|\n| fake_package"
                    " | badf00d   | tums       |\n| fake_package | badf00d   "
                    "| tums       |")
        self.assertEqual(output, expected)


class TestDeploymentOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.deployments = [
            # dict(
            #     package=,
            #     environment=,
            #     by_apptype=[dict(
            #         current_app_deployment=,
            #         previous_app_deployment=,
            #         host_deployments=,
            #     )],
            # ),
            # dict(
            #     package=,
            #     environment=,
            #     by_apptype=[dict(
            #         current_app_deployment=,
            #         previous_app_deployment=,
            #         host_deployments=,
            #     )],
            # ),
        ]
        self.CLI = cli.CLI("blocks")

    @patch('tds.views.cli.format_deployments')
    def test_generate_deploy_show_result(self, format_deployments):
        self.CLI.generate_deploy_show_result(result=self.deployments)
        format_deployments.assert_called_with(self.deployments)


class TestExceptionOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.CLI = cli.CLI("blocks")

    @patch('tds.views.cli.format_exception')
    def test_generate_deploy_show_result_error(self, format_exception):
        self.CLI.generate_deploy_show_result(error=1)
        format_exception.assert_called_with(1)

    @patch('tds.views.cli.format_exception')
    def test_generate_application_add_result_error(self, format_exception):
        self.CLI.generate_application_add_result(error=1)
        format_exception.assert_called_with(1)

    @patch('tds.views.cli.format_exception')
    def test_generate_application_delete_result_error(self, format_exception):
        self.CLI.generate_application_delete_result(error=1)
        format_exception.assert_called_with(1)

    @patch('tds.views.cli.format_exception')
    def test_generate_project_add_result_error(self, format_exception):
        self.CLI.generate_project_add_result(error=1)
        format_exception.assert_called_with(1)

    @patch('tds.views.cli.format_exception')
    def test_generate_project_delete_result_error(self, format_exception):
        self.CLI.generate_project_delete_result(error=1)
        format_exception.assert_called_with(1)

    @patch('tds.views.cli.format_exception')
    def test_generate_default_result_error(self, format_exception):
        self.CLI.generate_default_result(error=1)
        format_exception.assert_called_with(1)

    def test_format_exception_access_error(self):
        class AccessError(Exception):
            pass

        error = AccessError()
        output = cli.format_exception(error)
        self.assertEqual(
            ("You do not have the appropriate permissions to run this command"
             ". Contact your manager."),
            output
        )

    def test_format_exception_default_error(self):
        error = Exception("Whoopsies")
        output = cli.format_exception(error)
        self.assertEqual(
            "Whoopsies",
            output
        )

    def test_format_exception_broken_error(self):
        error = Exception()
        output = cli.format_exception(error)
        self.assertEqual(
            ("Exception=repr(Exception()) str() could not be formatted: "
             "IndexError('tuple index out of range',)"),
            output
        )


class TestProjectOutputFormatter(unittest.TestCase):

    def setUp(self):
        self.projects = [ProjectFactory(name="proj1"),
                         ProjectFactory(name="proj2")]
        self.CLI = cli.CLI("blocks")
        sys.stdout = self.out = StringIO()

    @patch('tds.views.cli.format_project')
    def test_generate_project_list_result(self, format_project):
        self.CLI.generate_project_list_result(result=self.projects)
        format_project.assert_called_with(self.projects, "blocks")

    @patch('tds.views.cli.format_project')
    def test_generate_project_add_result(self, format_project):
        self.CLI.generate_project_add_result(result=self.projects[0])
        self.assertIn(
            'Created {s.name}:'.format(s=self.projects[0]),
            self.out.getvalue()
        )
        format_project.assert_called_with(self.projects[0], "blocks")

# TODO: Write this test suite more fully
#
#     def test_single_proj_blocks_format(self):
#         output = cli.format_project(self.projects[0])
#         self.assertEqual(output, ...)
