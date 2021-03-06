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

Feature: GET package(s) from the REST API
    As a developer
    I want information on packages
    So that I can be informed of the current state of the database

    Background:
        Given there are applications:
            | name  |
            | app1  |
            | app2  |
        And there are packages:
            | version   | revision  |
            | 1         | 2         |
            | 2         | 1         |
            | 2         | 2         |
            | 2         | 3         |
            | 3         | 1         |
        And I have a cookie with user permissions

    @rest
    Scenario Outline: no application
        When I query GET "/applications/<select>/<pkg_select>"
        Then the response code is 404
        And the response contains errors:
            | location  | name          | description                                   |
            | path      | name_or_id    | Application with <descript> does not exist.   |

        Examples:
            | select    | pkg_select    | descript      |
            | noexist   | packages      | name noexist  |
            | noexist   | packages/1/1  | name noexist  |
            | 5         | packages      | ID 5          |
            | 5         | packages/1/1  | ID 5          |

    @rest
    Scenario Outline: no packages
        When I query GET "/applications/<select>/packages"
        Then the response code is 200
        And the response is a list of 0 items

        Examples:
            | select    |
            | app1      |
            | 2         |

    @rest
    Scenario Outline: get all packages for an application
        When I query GET "/applications/<select>/packages"
        Then the response code is 200
        And the response is a list of 5 items
        And the response list contains objects:
            | version   | revision  |
            | 1         | 2         |
            | 2         | 1         |
            | 2         | 2         |
            | 2         | 3         |
            | 3         | 1         |
        And the response list objects do not contain attributes creator

        Examples:
            | select    |
            | app2      |
            | 3         |

    @rest
    Scenario Outline: get all packages for an application with select query
        When I query GET "/applications/<select>/packages?select=version,revision"
        Then the response code is 200
        And the response is a list of 5 items
        And the response list contains objects:
            | version   | revision  |
            | 1         | 2         |
            | 2         | 1         |
            | 2         | 2         |
            | 2         | 3         |
            | 3         | 1         |
        And the response list objects do not contain attributes id,application_id,status,created,builder,user,name

        Examples:
            | select    |
            | app2      |
            | 3         |

    @rest
    Scenario Outline: get a package that doesn't exist for an application that does exist
        When I query GET "/applications/<select>/packages/<ver>/<rev>"
        Then the response code is 404
        And the response contains errors:
            | location  | name      | description                                                                           |
            | path      | revision  | Package with version <ver> and revision <rev> does not exist for this application.    |

        Examples:
            | select    | ver   | rev   |
            | app2      | 5     | 1     |
            | app2      | 1     | 5     |
            | 3         | 5     | 1     |
            | 3         | 1     | 5     |

    @rest
    Scenario Outline: get a specific package
        When I query GET "/applications/<select>/packages/<ver>/<rev>"
        Then the response code is 200
        And the response is an object with version="<ver>",revision="<rev>"

        Examples:
            | select    | ver   | rev   |
            | app2      | 1     | 2     |
            | app2      | 2     | 1     |
            | 3         | 1     | 2     |
            | 3         | 2     | 1     |

    @rest
    Scenario Outline: get a specific package with select query
        When I query GET "/applications/<select>/packages/<ver>/<rev>?select=version,revision"
        Then the response code is 200
        And the response is an object with version="<ver>",revision="<rev>"
        And the response object does not contain attributes id,application_id,status,created,builder,user

        Examples:
            | select    | ver   | rev   |
            | app2      | 1     | 2     |
            | app2      | 2     | 1     |
            | 3         | 1     | 2     |
            | 3         | 2     | 1     |

    @rest
    Scenario Outline: specify unknown query
        When I query GET "/applications/<select>/packages?<query>"
        Then the response code is 422
        And the response contains errors:
            | location  | name  | description                                                               |
            | query     | foo   | Unsupported query: foo. Valid parameters: ['limit', 'select', 'start'].   |

        Examples:
            | select    | query             |
            | app2      | foo=bar           |
            | app2      | limit=10&foo=bar  |
            | app2      | foo=bar&start=2   |
            | 3         | foo=bar           |
            | 3         | limit=10&foo=bar  |
            | 3         | foo=bar&start=2   |

    @rest
    Scenario Outline: specify limit and/or last queries
        When I query GET "/applications/<select>/packages?limit=<limit>&start=<start>"
        Then the response code is 200
        And the response is a list of <num> items
        And the response list contains id range <min> to <max>

        Examples:
            | select    | limit | start | num   | min   | max   |
            | app2      |       |       | 5     | 1     | 5     |
            | app2      |       | 1     | 5     | 1     | 5     |
            | app2      | 10    |       | 5     | 1     | 5     |
            | app2      | 4     | 1     | 4     | 1     | 4     |
            | 3         |       |       | 5     | 1     | 5     |
            | 3         |       | 2     | 4     | 2     | 5     |
            | 3         | 10    |       | 5     | 1     | 5     |
            | 3         | 4     | 1     | 4     | 1     | 4     |
