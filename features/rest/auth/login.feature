Feature: Login
    As a developer
    I want to login
    So that I can have access to interact with the REST API

    @rest
    Scenario Outline: insufficient parameters
        When I POST "{<body>}" to "/login"
        Then the response code is 400
        And the response contains errors:
            | location  | name  | description                                                                                               |
            | body      |       | Could not parse body as valid JSON. Body must be a JSON object with attributes "username" and "password". |

        Examples:
            | body              |
            |                   |
            | "password": "bar" |
            | "username": "foo" |

    @rest
    Scenario: invalid credentials
        When I POST "{"username": "horsefeathers", "password": "hensteeth"}" to "/login"
        Then the response code is 401
        And the response does not contain a cookie
        And the response contains errors:
            | location  | name      | description                                                                   |
            | query     | user      | Authentication failed. Please check your username and password and try again. |

    @rest @ldap_off
    Scenario: LDAP server not accessible
        When I POST "{"username": "horsefeathers", "password": "hensteeth"}" to "/login"
        Then the response code is 500
        And the response contains errors:
            | location  | name  | description                       |
            | url       |       | Could not connect to LDAP server. |

    @rest
    Scenario: valid credentials
        When I POST "{"username": "testuser", "password": "secret"}" to "/login"
        Then the response code is 200
        And the response contains a cookie

    @rest
    Scenario Outline: specify method permissions
        When I POST "{"username": "testuser", "password": "secret", "methods": "<methods>"}" to "/login"
        Then the response code is 200
        And the response contains a cookie with methods=<methods>

        Examples:
            | methods           |
            | GET               |
            | GET+POST          |
            | GET+POST+DELETE   |

    @rest
    Scenario: attempt to get a wildcard cookie without authorization
        When I POST "{"username": "testuser", "password": "secret", "wildcard": true}" to "/login"
        Then the response code is 403
        And the response contains errors:
            | location  | name      | description                                               |
            | body      | wildcard  | Insufficient authorization. NO WILDCARD COOKIES FOR YOU!  |

    @rest
    Scenario Outline: get a wildcard cookie
        Given "testuser" is a wildcard user in the REST API
        When I POST "{"username": "testuser", "password": "secret", "wildcard": <bool>}" to "/login"
        Then the response code is 200
        And the response contains a cookie

        Examples:
            | bool  |
            | true  |
            | 1     |

    @rest
    Scenario: attempt to get an env-specific cookie for an environment that doesn't exist
        When I POST "{"username": "testuser", "password": "secret", "environments": "1"}" to "/login"
        Then the response code is 400
        And the response contains errors:
            | location  | name          | description                           |
            | body      | environments  | Could not find environment with ID 1. |

    @rest
    Scenario Outline: get an env-specific cookie
        Given there is an environment with name="dev"
        And there is an environment with name="stage"
        And there is an environment with name="prod"
        When I POST "{"username": "testuser", "password": "secret", "environments": "<envs>"}" to "/login"
        Then the response code is 200
        And the response contains a cookie with environments=<envs>

        Examples:
            | envs  |
            | 1     |
            | 1+2   |
            | 1+2+3 |
