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

Feature: deploy promote application version [-f|--force] [--delay] [--hosts|--apptypes|--all-apptypes] [--detach] (-f/--force only for deploy promote)
    As a developer
    I want to deploy applications to targets
    So that I can update services easily

    Background:
        Given I have "stage" permissions
        And there are environments
            | name   |
            | dev    |
            | stage  |
        And I am in the "stage" environment
        And there is a project with name="proj"
        And there is an application with name="myapp"
        And there is a deploy target with name="the-apptype"
        And there are packages:
            | version   | revision  |
            | 121       | 1         |
            | 122       | 1         |
            | 123       | 1         |
        And there are deployments:
            | id    | user  | status    |
            | 1     | foo   | complete  |
            | 2     | foo   | complete  |
        And there are tier deployments:
            | id    | deployment_id | environment_id    | status    | user  | app_id    | package_id    |
            | 1     | 1             | 1                 | validated | foo   | 2         | 1             |
        And I wait 1 seconds
        And there are tier deployments:
            | id    | deployment_id | environment_id    | status    | user  | app_id    | package_id    |
            | 2     | 2             | 2                 | validated | foo   | 2         | 2             |
        And I wait 1 seconds
        And there are tier deployments:
            | id    | deployment_id | environment_id    | status    | user  | app_id    | package_id    |
            | 3     | 1             | 1                 | validated | foo   | 2         | 3             |
        And there are hosts:
            | name          | env   | app_id    |
            | dprojhost01   | dev   | 2         |
            | dprojhost02   | dev   | 2         |
            | sprojhost01   | stage | 2         |
            | sprojhost02   | stage | 2         |
        And the tier "the-apptype" is associated with the application "myapp" for the project "proj"

    Scenario: promote application that doesn't exist
        When I run "deploy promote badapp 456 --detach"
        Then the output is "Application does not exist: badapp"

    Scenario: promote version that doesn't exist
        When I run "deploy promote myapp 456 --detach"
        Then the output is "Package does not exist: myapp@456"

    Scenario: promote version to host that doesn't exist
        When I run "deploy promote myapp 123 --hosts badhost01 --detach"
        Then the output has "Host does not exist: badhost01"

    Scenario: promote version to apptype that doesn't exist
        When I run "deploy promote myapp 123 --apptype bad-apptype --detach"
        Then the output has "Valid apptypes for application "myapp" are: ['the-apptype']"

    Scenario: promote version to apptype that's not a part of the project
        Given there is a deploy target with name="other-apptype"
        When I run "deploy promote myapp 123 --apptype other-apptype --detach"
        Then the output has "Valid apptypes for application "myapp" are: ['the-apptype']"

    Scenario: promote version that isn't validated in previous env (only for deploy)
        Given there is a package with version="124"
        When I run "deploy promote myapp 124 --detach"
        Then the output has "Application "myapp", version "124" is not validated in the previous environment for tier "the-apptype", skipping..."

    Scenario: promote version to hosts
        When I run "deploy promote myapp 123 --hosts sprojhost01 sprojhost02 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=3,package_id=3,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=4,package_id=3,duration=0

    Scenario: promote older version to hosts
        When I run "deploy promote myapp 121 --hosts sprojhost01 sprojhost02 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=3,package_id=1,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=4,package_id=1,duration=0

    Scenario: promote version to apptype
        When I run "deploy promote myapp 123 --apptype the-apptype --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=3,app_id=2,package_id=3,environment_id=2,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=3,package_id=3,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=4,package_id=3,duration=0
        And there is no tier deployment with deployment_id=3,environment_id=1
        And there is no host deployment with deployment_id=3,host_id=1
        And there is no host deployment with deployment_id=3,host_id=2

    Scenario: promote olders version to apptype
        When I run "deploy promote myapp 121 --apptype the-apptype --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=3,app_id=2,package_id=1,environment_id=2,duration=0

    Scenario: promote version to all apptypes
        Given there is a deploy target with name="another-apptype"
        And there is a host with name="anotherhost01"
        And the host is associated with the deploy target
        And the tier "another-apptype" is associated with the application "myapp" for the project "proj"
        And there are tier deployments:
            | id    | deployment_id | environment_id    | status    | user  | app_id    | package_id    |
            | 4     | 2             | 1                 | validated | foo   | 3         | 3             |
        When I run "deploy promote myapp 123 --all-apptypes --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=3,app_id=2,package_id=3,environment_id=2,duration=0
        And there is a tier deployment with status="pending",deployment_id=3,app_id=3,package_id=3,environment_id=2,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=3,package_id=3,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=4,package_id=3,duration=0
        And there is a host deployment with status="pending",deployment_id=3,host_id=5,package_id=3,duration=0
        And there is no tier deployment with deployment_id=3,environment_id=1
        And there is no host deployment with deployment_id=3,host_id=1
        And there is no host deployment with deployment_id=3,host_id=2

    Scenario: promote older version to all apptypes
        Given there is a deploy target with name="another-apptype"
        And there is a host with name="anotherhost01"
        And the host is associated with the deploy target
        And the tier "another-apptype" is associated with the application "myapp" for the project "proj"
        And the package "121" is deployed on the deploy targets in the "dev" env
        And the package "121" has been validated in the "development" environment
        When I run "deploy promote myapp 121 --all-apptypes --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=4,app_id=2,package_id=1,environment_id=2,duration=0
        And there is a tier deployment with status="pending",deployment_id=4,app_id=3,package_id=1,environment_id=2,duration=0

    Scenario: promote version to all apptypes with delay option
        When I run "deploy promote myapp 123 --delay 10 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with id=3,status="queued",delay=10,duration=0
        And there is a tier deployment with deployment_id=3,status="pending",app_id=2,package_id=3,environment_id=2,duration=0

    Scenario Outline: promote version that isn't validated in previous env with force option
        Given there is a package with version="124"
        When I run "deploy promote <switch> myapp 124 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=3,app_id=2,package_id=4,environment_id=2,duration=0

        Examples:
            | switch    |
            | -f        |
            | --force   |

    Scenario: promote a version that has already been deployed
        Given the package is deployed on the deploy targets in the "stage" env
        When I run "deploy promote myapp 123 --detach"
        Then the output has "Application "myapp", version "123" is currently deployed on tier "the-apptype", skipping..."

    Scenario: promote a version that has already been validated
        Given the package is deployed on the deploy targets in the "stage" env
        And the package has been validated in the "staging" environment
        When I run "deploy promote myapp 123 --detach"
        Then the output has "Application "myapp", version "123" is currently deployed on tier "the-apptype", skipping..."

    Scenario: deploying to multiple hosts of different apptypes
        Given there is a deploy target with name="other-apptype"
        And there are hosts:
            | name       | env    |
            | dother01   | dev    |
            | dother02   | dev    |
            | sother01   | stage  |
            | sother02   | stage  |
        And the hosts are associated with the deploy target
        And the deploy target is a part of the project-application pair
        And there is a package with version="124"
        And the package is deployed on the deploy targets in the "dev" env
        And the package has been validated in the "development" environment
        When I run "deploy promote myapp 124 --hosts sprojhost01 sprojhost02 sother01 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=3,package_id=4,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=4,package_id=4,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=7,package_id=4,duration=0

    Scenario: deploying older version to multiple hosts of different apptypes
        Given there is a deploy target with name="other-apptype"
        And there are hosts:
            | name       | env    |
            | dother01   | dev    |
            | dother02   | dev    |
            | sother01   | stage  |
            | sother02   | stage  |
        And the hosts are associated with the deploy target
        And the deploy target is a part of the project-application pair
        And the package "121" is deployed on the deploy targets in the "dev" env
        And the package "121" has been validated in the "development" environment
        When I run "deploy promote myapp 121 --hosts sprojhost01 sprojhost02 sother01 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=3,package_id=1,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=4,package_id=1,duration=0
        And there is a host deployment with status="pending",deployment_id=4,host_id=7,package_id=1,duration=0

    Scenario: promote to an apptype with version already deployed to hosts
        Given there are deployments:
            | id    | user  | status    |
            | 3     | foo   | complete  |
        And I wait 1 seconds
        And there are host deployments:
            | id    | deployment_id | host_id   | status    | user  | package_id    |
            | 1     | 3             | 3         | ok        | foo   | 3             |
            | 2     | 3             | 4         | ok        | foo   | 3             |
        When I run "deploy promote myapp 123 --apptype the-apptype --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=4,app_id=2,package_id=3,environment_id=2,duration=0
        And there is no host deployment with deployment_id=4

    Scenario: with the most recent tier dep invalidated
        Given there are deployments:
            | id    | user  | status    |
            | 3     | foo   | complete  |
            | 4     | foo   | failed    |
        And there are packages:
            | version   | revision  |
            | 124       | 1         |
        And I wait 1 seconds
        And there are tier deployments:
            | id    | deployment_id | app_id    | status        | user  | package_id    | environment_id    |
            | 4     | 3             | 2         | validated     | foo   | 4             | 1                 |
            | 5     | 4             | 2         | invalidated   | foo   | 4             | 2                 |
        And there are host deployments:
            | id    | deployment_id | host_id   | status    | user  | package_id    |
            | 1     | 4             | 3         | ok        | foo   | 4             |
            | 2     | 4             | 4         | failed    | foo   | 4             |
        When I run "deploy promote myapp 124 --apptype the-apptype --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with id=5,status="queued",delay=0,duration=0
        And there is a tier deployment with status="pending",deployment_id=5,app_id=2,package_id=4,environment_id=2,duration=0
        And there is a host deployment with status="pending",deployment_id=5,host_id=4,package_id=4,duration=0
        And there is no host deployment with host_id=3,deployment_id=5
