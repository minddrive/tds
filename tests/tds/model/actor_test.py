'''Tests for the actor model'''

import os
import pwd
import unittest2

from mock import Mock, mock_open, patch

import tds.model


class TestActorModel(unittest2.TestCase):
    'Tests for actor model'

    def setUp(self):
        self.actor = tds.model.Actor()

        self.actor_properties = {
            'name': 'fake_user',
            'groups': ['fake_group1', 'fake_group2'],
        }

    def tearDown(self):
        patch.stopall()

    def test_name(self):
        'Ensure "name" property is functional'
        getuid = patch(
            'os.getuid',
            return_value = 1234
        ).start()
        getpwuid = patch(
            'pwd.getpwuid',
            return_value = [self.actor_properties['name']]
        ).start()

        assert self.actor.name == self.actor_properties['name']

    def get_group_names(self, gid):
        'Method to return fake group name for fake gid'
        if gid == 501:
            return Mock(gr_name='fake_group1')
        elif gid == 502:
            return Mock(gr_name='fake_group2')
        else:
            return None

    def test_groups(self):
        'Ensure "groups" property is functional'
        getgroups = patch(
            'os.getgroups',
            return_value = [501, 502]
        ).start()

        getgrgid = patch(
            'grp.getgrgid',
            side_effect = self.get_group_names
        ).start()

        assert self.actor.groups == self.actor_properties['groups']
