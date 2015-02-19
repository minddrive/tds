Feature: Update (PUT) project on REST API
    As a developer
    I want to update information for one of my projects
    So that the database has the proper information

    Background:
        Given there are projects:
            | name  |
            | proj1 |
            | proj2 |
            | proj3 |

    @rest
    Scenario Outline: update a project that doesn't exist
        When I query PUT "/projects/<select>?name=newname"
        Then the response code is 404
        And the response contains errors:
            | location  | name          | description                               |
            | path      | name_or_id    | Project with <descript> does not exist.   |

        Examples:
            | select    | descript      |
            | noexist   | name noexist  |
            | 500       | ID 500        |

    @rest
    Scenario Outline: update a project
        When I query PUT "/projects/<select>?name=newname"
        Then the response code is 200
        And the response is an object with name="newname",id=2
        And there is a project with name="newname",id=2

        Examples:
            | select    |
            | proj2     |
            | 2         |

    @rest
    Scenario Outline: pass an invalid parameter
        When I query PUT "/projects/<select>?<query>"
        Then the response code is 400
        And the response contains errors:
            | location  | name  | description                                                                                                   |
            | query     | foo   | Unsupported query: foo. Valid parameters: ['package_definitions', 'applications', 'targets', 'name', 'id'].   |
        And there is a project with name="proj2",id=2

        Examples:
            | select    | query                 |
            | proj2     | foo=bar               |
            | 2         | foo=bar               |
            | proj2     | name=newname&foo=bar  |
            | 2         | name=newname&foo=bar  |
            | proj2     | foo=bar&name=newname  |
            | 2         | foo=bar&name=newname  |
