Feature: Malformed cookie detection
    As an API developer
    I want to prevent users from modifying cookies to bypass authorization
    So that the API can be secure

    @rest
    Scenario: attempt to overwrite user
        Given I have a cookie with user permissions
        And I set the cookie user to "testadmin"
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |

    @rest
    Scenario: attempt to overwrite environment restrictions
        Given there is an environment with name="dev"
        And I have a cookie with user permissions and environments=1
        And I set the cookie environments to 1+2
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |

    @rest
    Scenario: attempt to overwrite method restrictions
        Given I have a cookie with user permissions and methods=GET
        And I set the cookie methods to GET+POST
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |

    @rest
    Scenario: attempt to remove user
        Given I have a cookie with user permissions
        And I remove user from the cookie
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |

    @rest
    Scenario: attempt to remove environment restrictions
        Given there is an environment with name="dev"
        And I have a cookie with user permissions and environments=1
        And I remove environments from the cookie
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |

    @rest
    Scenario: attempt to remove method restrictions
        Given I have a cookie with user permissions and methods=GET
        And I remove methods from the cookie
        When I query GET "/projects"
        Then the response code is 419
        And the response contains errors:
            | location  | name      | description                                               |
            | header    | cookie    | Cookie has expired or is invalid. Please reauthenticate.  |
