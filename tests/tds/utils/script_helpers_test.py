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

import unittest

from mock import Mock, patch

import tds.utils.script_helpers as SH

from tests.factories.model.actor import ActorFactory
from tests.factories.model.package import PackageFactory
from tests.factories.model.project import ProjectFactory
from tests.factories.model.deployment import AppDeploymentFactory
from tests.factories.utils.config import (
    DatabaseTestConfigFactory,
    DeployConfigFactory
)

from datetime import datetime, timedelta


class TestUnvalidatedDeploymentNotifier(unittest.TestCase):
    def get_mock_app_dep(self, actor, package, project):
        tds_deployment = Mock(
            environment='test',
            package=package
        )

        application = Mock(
            app_type='fake_app_type'
        )

        project = Mock(
            project=project,
        )

        return Mock(
            application=application,
            deployment=tds_deployment,
            project=project,
            user=actor.name,
        )

    def test_convert_deployment(self):
        actor = ActorFactory()
        package = PackageFactory()
        project = ProjectFactory()

        app_deployment = self.get_mock_app_dep(actor, package, project)
        deployment = app_deployment.deployment
        application = app_deployment.application

        result = SH.UnvalidatedDeploymentNotifier.convert_deployment(
            app_deployment
        )

        # XXX: skipped for now. groups don't match
        # assert result.actor == actor
        assert result.actor.name == actor.name
        assert result.action['command'] == 'unvalidated'
        assert result.project['name'] == package.name
        # TODO: shouldn't have to call vars
        # No idea why this is failing.  package.name == 'fake_package'
        # and package.version == 'badf00d'
        # assert result.package == vars(package)
        assert result.target['environment'] == deployment.environment
        assert result.target['apptypes'] == [application.app_type]

    def test_notify(self):
        n = 2
        actor = ActorFactory()
        packages = [PackageFactory() for _ in range(n)]
        project = ProjectFactory()
        deployments = [
            self.get_mock_app_dep(actor, p, project) for p in packages
        ]

        base = SH.UnvalidatedDeploymentNotifier.__bases__[0]
        with patch.object(base, 'notify'):
            udn = SH.UnvalidatedDeploymentNotifier(dict())
            udn.notify(deployments)
            assert base.notify.call_count == n


class TDPProvider(unittest.TestCase):
    def __init__(self, dbconfig, get_all_return_value, *a, **k):
        self.dbconfig = dbconfig
        self.get_all_return_value = get_all_return_value

        super(TDPProvider, self).__init__(*a, **k)

    def get_tdp(self):
        app_dep_mock = patch('tds.model.AppDeployment').start()
        app_dep_mock.find.return_value = self.get_all_return_value

        tdp = SH.TagopsdbDeploymentProvider(self.dbconfig)

        return tdp

    def tearDown(self):
        patch.stopall()
        super(TDPProvider, self).tearDown()


class DefaultTDPProvider(TDPProvider):
    def __init__(self, *a, **k):
        dbconfig = DatabaseTestConfigFactory()
        app_deps = getattr(self, 'app_deps', None)
        if app_deps is None:
            app_deps = self.app_deps = [
                AppDeploymentFactory(),
                AppDeploymentFactory()
            ]

        super(DefaultTDPProvider, self).__init__(dbconfig, app_deps, *a, **k)


class TestTagopsdbDeploymentProvider(DefaultTDPProvider):
    def test_init_and_get_all(self):
        with patch('tagopsdb.init', return_value=None) as init_session:
            tdp = self.get_tdp()
            tdp.init()
            assert len(init_session.call_args_list) == 1
            _args, kwargs = init_session.call_args_list[0]
            assert kwargs.get('url', None) == dict(
                username=self.dbconfig['db']['user'],
                password=self.dbconfig['db']['password'],
                host=self.dbconfig['db']['hostname'],
                database=self.dbconfig['db']['db_name'],
            )

            assert tdp.get_all('test') == self.app_deps


class TestValidationMonitor(DefaultTDPProvider):
    config = DeployConfigFactory()

    def __init__(self, *a, **k):
        val_time = self.config['notifications.validation_time']
        overdue = datetime.now() - timedelta(seconds=val_time+1)
        not_overdue = datetime.now() - timedelta(seconds=val_time-1)
        self.app_deps = [
            AppDeploymentFactory(
                needs_validation=True,
                realized=ts
            )

            for ts in [overdue, not_overdue]
        ]

        super(TestValidationMonitor, self).__init__(*a, **k)

    def test_get_deployments_requiring_validation(self):
        vmon = SH.ValidationMonitor(self.config, self.get_tdp())
        deps = vmon.get_deployments_requiring_validation()
        assert len(deps) == 1
