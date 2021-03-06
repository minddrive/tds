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

Feature: Ongoing deployments blocking attempted new ones
    As a developer
    I don't want to clobber ongoing deployments
    So that there's less violence in the world

    Background:
        Given there are environments
            | name   |
            | dev    |
            | stage  |

    Scenario Outline: promote with ongoing apptype deployment
        Given I have "dev" permissions
        And I am in the "dev" environment
        And there is a project with name="proj"
        And there is an application with name="myapp"
        And there is a deploy target with name="the-apptype"
        And there is a package with version="123"
        And there are hosts:
            | name          | env   |
            | dprojhost01   | dev   |
            | dprojhost02   | dev   |
        And the deploy target is a part of the project-application pair
        And the hosts are associated with the deploy target
        And there is an ongoing deployment on the deploy target
        And there is a package with version="124"
        When I run "deploy promote myapp 124 <targets> --detach"
        Then the output has "currently running a deployment for the tier the-apptype in the development environment. Skipping..."
        And there is no deployment with id=2
        And there is no tier deployment with deployment_id=2
        And there is no host deployment with deployment_id=2

    Examples:
        | targets                   |
        | --hosts dprojhost01       |
        | --all-apptypes            |
        | --apptypes the-apptype    |

    Scenario Outline: promote with ongoing host deployment
        Given I have "dev" permissions
        And I am in the "dev" environment
        And there is a project with name="proj"
        And there is an application with name="myapp"
        And there is a deploy target with name="the-apptype"
        And there is a package with version="123"
        And there are hosts:
            | name          | env   |
            | dprojhost01   | dev   |
            | dprojhost02   | dev   |
        And the deploy target is a part of the project-application pair
        And the hosts are associated with the deploy target
        And there is an ongoing deployment on the hosts="dprojhost01"
        When I run "deploy promote myapp 123 <targets> --detach"
        Then the output has "currently running a deployment for the host dprojhost01 in the development environment. Skipping..."
        And there is no deployment with id=2
        And there is no tier deployment with deployment_id=2
        And there is no host deployment with deployment_id=2

    Examples:
        | targets                   |
        | --hosts dprojhost01       |
        | --all-apptypes            |
        | --apptypes the-apptype    |

    Scenario: promote with ongoing host deployment on a different host
        Given I have "dev" permissions
        And I am in the "dev" environment
        And there is a project with name="proj"
        And there is an application with name="myapp"
        And there is a deploy target with name="the-apptype"
        And there is a package with version="123"
        And there are hosts:
            | name          | env   |
            | dprojhost01   | dev   |
            | dprojhost02   | dev   |
        And the deploy target is a part of the project-application pair
        And the hosts are associated with the deploy target
        And there is an ongoing deployment on the hosts="dprojhost01"
        When I run "deploy promote myapp 123 --hosts dprojhost02 --detach"
        Then the output has "Deployment ready for installer daemon, disconnecting now."
        And there is a deployment with id=2,status="queued"
        And there is a host deployment with deployment_id=2,status="pending",host_id=2,package_id=1

    Scenario Outline: fix with ongoing apptype deployment
        Given I have "stage" permissions
        And I am in the "stage" environment
        And there is a project with name="proj"
        And there is an application with name="myapp"
        And there is a deploy target with name="the-apptype"
        And the deploy target is a part of the project-application pair
        And there are hosts:
            | name          | env     |
            | dprojhost01   | dev     |
            | dprojhost02   | dev     |
            | sprojhost01   | stage   |
            | sprojhost02   | stage   |
        And the hosts are associated with the deploy target

        And there is a package with version="122"
        And the package is deployed on the deploy targets in the "stage" env
        And the package has been validated in the "staging" environment

        And there is a package with version="123"
        And the package is deployed on the deploy targets in the "dev" env
        And the package has been validated in the "development" environment
        And the package is deployed on the deploy targets in the "stage" env
        And there is an ongoing deployment on the deploy target
        When I run "deploy fix myapp <targets> --detach"
        Then the output has "currently running a deployment for the tier the-apptype in the staging environment. Skipping..."
        And there is no deployment with id=3
        And there is no tier deployment with deployment_id=3
        And there is no host deployment with deployment_id=3

    Examples:
        | targets                   |
        | --hosts sprojhost02       |
        | --all-apptypes            |
        | --apptypes the-apptype    |
