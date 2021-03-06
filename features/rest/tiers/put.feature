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

Feature: PUT app tier(s) from the REST API
    As an admin
    I want to update an app tier
    So that database information reflects the current environment state

    Background:
        Given I have a cookie with admin permissions
        And there is a deploy target with name="tier1"
        And there is a deploy target with name="tier2"

    @rest
    Scenario Outline: update a tier
        When I query PUT "/tiers/<select>?<params>"
        Then the response code is 200
        And the response is an object with <props>

        Examples:
            | select    | params                    | props                                         |
            | tier2     |                           | name="tier2",id=3                             |
            | 3         |                           | name="tier2",id=3                             |
            | tier2     | status=inactive           | name="tier2",id=3,status="inactive"           |
            | 3         | status=inactive           | name="tier2",id=3,status="inactive"           |
            | tier2     | puppet_class=cls          | name="tier2",id=3,puppet_class="cls"          |
            | 3         | puppet_class=cls          | name="tier2",id=3,puppet_class="cls"          |
            | tier2     | distribution=centos7.1    | name="tier2",id=3,distribution="centos7.1"    |
            | 3         | distribution=centos7.1    | name="tier2",id=3,distribution="centos7.1"    |
            | 3         | name=tier100              | name="tier100",id=3                           |
            | tier2     | name=tier100              | name="tier100",id=3                           |

    @rest
    Scenario Outline: attempt to update a tier that doesn't exist
        When I query PUT "/tiers/<select>?name=tier100"
        Then the response code is 404
        And the response contains errors:
            | location  | name          | description                           |
            | path      | name_or_id    | Tier with <descript> does not exist.  |
        And there is no deploy target with name="tier100"

        Examples:
            | select    | descript      |
            | noexist   | name noexist  |
            | 500       | ID 500        |

    @rest
    Scenario Outline: pass an invalid parameter
        When I query PUT "/tiers/<select>?name=tier100&id=50&foo=bar"
        Then the response code is 422
        And the response contains errors:
            | location  | name  | description                                                                                                                   |
            | query     | foo   | Unsupported query: foo. Valid parameters: ['distribution', 'ganglia_id', 'ganglia_name', 'name', 'puppet_class', 'status'].   |
        And there is no deploy target with name="tier100"
        And there is no deploy target with id=4

        Examples:
            | select    |
            | tier2     |
            | 3         |
