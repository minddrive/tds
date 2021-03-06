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
from unittest_data_provider import data_provider

import unittest
import tds.notifications.base as base

from tests.factories.utils.config import DeployConfigFactory
from tests.factories.model.deployment import (
    DeploymentFactory,
    UnvalidatedDeploymentFactory,
    HostDeploymentFactory,
    AllApptypesDeploymentFactory,
)


class AppConfigProvider(unittest.TestCase):
    def setUp(self):
        self.app_config = DeployConfigFactory()
        self.config = self.app_config['notifications']


class TestNotifications(AppConfigProvider):

    def create_notification(self):
        return base.Notifications(self.app_config)

    def test_constructor(self):
        n = self.create_notification()

        self.assertEqual(n.config, self.config)
        self.assertEqual(n.enabled_methods, self.config['enabled_methods'])
        self.assertEqual(n.validation_time, self.config['validation_time'])

    @patch('tds.notifications.mail.EmailNotifier', autospec=True)
    @patch('tds.notifications.hipchat.HipchatNotifier', autospec=True)
    def test_send_notifications(self, hipchat, email):
        self.config['enabled_methods'] = ['email', 'hipchat']
        n = self.create_notification()

        notifiers = {
            'email': email,
            'hipchat': hipchat
        }

        deployment = DeploymentFactory()
        with patch.object(n, '_notifiers', notifiers):
            n.notify(deployment)

            for mock in notifiers.values():
                mock.return_value.notify.assert_called_with(deployment)


class TestNotifierClass(AppConfigProvider):
    def test_send(self):
        n = base.Notifier({}, {})
        self.assertRaises(
            NotImplementedError,
            n.notify,
            deployment=object()
        )

    deployment_factory_provider = lambda *a: [
        (
            DeploymentFactory,
            'Promote of version badf00d of fake_package on app tier(s)'
            ' fake_apptype in fakedev',
            'fake_user performed a "tds deploy promote" for the following app'
            ' tier(s) in fakedev:\n'
            '    fake_apptype'
        ),
        (
            HostDeploymentFactory,
            'Promote of version badf00d of fake_package on hosts'
            ' whatever.example.com in fakedev',
            'fake_user performed a "tds deploy promote" for the following'
            ' hosts in fakedev:\n'
            '    whatever.example.com'
        ),
        (
            AllApptypesDeploymentFactory,
            'Promote of version badf00d of fake_package on app tier(s)'
            ' fake_apptype1, fake_apptype2 in fakedev',
            'fake_user performed a "tds deploy promote" for the following app'
            ' tier(s) in fakedev:\n'
            '    fake_apptype1, fake_apptype2'
        ),
    ]

    @data_provider(deployment_factory_provider)
    def test_message_for_deploy_promote(
        self, deployment_factory, subject, body
    ):

        nots = base.Notifier(
            self.app_config,
            self.config
        )
        deployment = deployment_factory()
        message = nots.message_for_deployment(deployment)

        self.assertIsInstance(message['subject'], basestring)
        self.assertIsInstance(message['body'], basestring)

        # are these assertions really necessary?
        self.assertEqual(message['subject'], subject)
        self.assertEqual(message['body'], body)

    def test_message_for_unvalidated(self):
        n = base.Notifier(
            self.app_config,
            self.config
        )

        message = n.message_for_deployment(
            UnvalidatedDeploymentFactory()
        )
        self.assertIsInstance(message['subject'], basestring)
        self.assertIsInstance(message['body'], basestring)
        # do we want to assert any more here?
