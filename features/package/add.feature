Feature: package add application version [-f|--force]
    As a user
    I want to add a specific version of a package
    So I can deploy that version of that package to targets

    Background:
        Given I have "dev" permissions
        And there is an environment with name="dev"
        And I am in the "dev" environment

    Scenario: too few arguments
        When I run "package add myapp"
        Then the output has "usage:"

    Scenario: too many arguments
        When I run "package add myapp vers foo"
        Then the output has "usage:"

    Scenario: add a package to an application that doesn't exist
        When I run "package add myapp 123"
        Then the output is "Application does not exist: myapp"

    Scenario: add a package with force flag should not succeed
        Given there is an application with name="myapp"
        When I run "package add --force myapp 123"
        Then the output has "Force not implemented yet"

    Scenario: attempt to add package when jenkins is not accessible
        Given there is an application with name="myapp"
        When I run "package add myapp 123"
        Then the output has "Unable to contact Jenkins server"
        And there is a package with name="myapp",version="123",status="failed"

    @jenkins_server
    Scenario: add a package to an application with a job name that doesn't exist
        Given there is an application with name="myapp"
        When I run "package add myapp 123"
        Then the output has "Job does not exist: job"
        And there is a package with name="myapp",version="123",status="failed"

    @jenkins_server
    Scenario: add a package to an application with a version that doesn't exist
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        When I run "package add myapp 123"
        Then the output has "Build does not exist on http://localhost"
        And the output has "job@123"
        And there is a package with name="myapp",version="123",status="failed"

    @jenkins_server
    Scenario: with --job flag indicating a non-existent job
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        When I run "package add --job another_job myapp 123"
        Then the output has "Job does not exist: another_job"
        And there is a package with name="myapp",version=123,status="failed"

    @jenkins_server
    Scenario: add a package that has previously failed to an application
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        And there is a package with name="myapp",version="123",status="failed"
        When I start to run "package add myapp 123"
        And I wait 5 seconds
        And the status is changed to "completed" for package with name="myapp",version="123"
        And I wait 5 seconds
        And the command finishes
        Then the output has "Added package: "myapp@123""

    @jenkins_server
    Scenario: add a package to an application
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        When I start to run "package add myapp 123"
        And I wait 5 seconds
        And the status is changed to "completed" for package with name="myapp",version="123"
        And I wait 5 seconds
        And the command finishes
        Then the output has "Added package: "myapp@123""

    @jenkins_server
    Scenario: with explicit --job flag
        Given there is an application with name="myapp"
        And there is a jenkins job with name="another_job"
        And the job has a build with number="123"
        When I start to run "package add --job another_job myapp 123"
        And I wait 5 seconds
        And the status is changed to "completed" for package with name="myapp",version="123"
        And I wait 5 seconds
        And the command finishes
        Then the output has "Added package: "myapp@123""

    @jenkins_server
    Scenario: override default job with explicit --job flag
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And there is a jenkins job with name="another_job"
        And the job has a build with number="123"
        When I start to run "package add --job another_job myapp 123"
        And I wait 5 seconds
        And the status is changed to "completed" for package with name="myapp",version="123"
        And I wait 5 seconds
        And the command finishes
        Then the output has "Added package: "myapp@123""

    @jenkins_server
    Scenario: package status was changed to 'failed' by repo updater
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        When I start to run "package add myapp 123"
        And I wait 5 seconds
        And the status is changed to "failed" for package with name="myapp",version="123"
        And I wait 5 seconds
        And the command finishes
        Then the output has "Failed to update repository with package for application "myapp", version 123."

    @jenkins_server
    Scenario: add a package to an application again
        Given there is an application with name="myapp"
        And there is a package with version="123"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        When I run "package add myapp 123"
        Then the output has "Package "myapp@123-1" already exists"

    @jenkins_server
    Scenario: add a package to an application where actual package isn't available
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        And jenkins does not have the job's artifact
        When I run "package add myapp 123"
        Then the output has "Artifact does not exist on http://localhost"
        And the output has "job@123"

    @jenkins_server
    Scenario: add a package to an application where repo update daemon fails to return in time
        Given there is an application with name="myapp"
        And there is a jenkins job with name="job"
        And the job has a build with number="123"
        When I start to run "package add myapp 123"
        And I wait 16 seconds
        And the command finishes
        Then the output has "Please open a JIRA issue in the TDS project."

    # TODO: There are probably more failure tests that can be written here!
    # e.g. test for already-exists package in various states: completed, pending, processing, removed, failed

    # Scenario: after failure, make sure can still add
