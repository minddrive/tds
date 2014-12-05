# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
# adding a package
# adding an invalid package (broken rpm) -- make sure it gets removed
# interrupted while adding a package
# file can't be removed
# test config loading and failure modes
# emails for invalid RPMs
# fail to send email for invalid RPMs
# package entry does not exist
# file is correctly moved
# failure to move file (file should be removed and package status failed)
# package is added correctly and is set to processing
# test race condition with package entry being invalidated in various ways
# test race condition with file being removed before repo update
# test multiple copies and failures -- status should be failed and file removed on final failure
# umask is set correctly when running make (for yum repo)
# make is run properly (package should be added successfully)
# make fails once (package should be added successfully)
# make fails twice (package status should be set to failed, file removed)
# files are all removed from processing
# after failure, make sure can still add

# note: test with single and multiple packages

Feature: YUM repo updater
    As a developer
    I want to have the YUM repo updated and handling files correctly
    So that I can be certain that the packages I add are actually added

    Background:
        Given there is an application with name="myapp"
        And there is a package with version="123"

    @repo_updater_daemon
    Scenario: adding a package
        Given there is an RPM package with name="myapp",version="123",revision="1",arch="noarch"
        And make will return 0
        When I run "daemon"
        Then the "incoming" directory is empty

    # Scenario: adding an invalid package (broken rpm)

    # Scenario: interrupt while adding a package

    # Scenario: file can't be removed

    # Scenario: test config loading and failure modes

    # Scenario: emails for invalid RPMs

    # Scenario: fail to send email for invalid RPMs

    # Scenario: package entry does not exist

    # Scenario: file is correctly moved

    # Scenario: failure to move file

    # Scenario: package is added correctly and is set to processing

    # Scenario: race condition with package entry being invalidated in various ways

    # Scenario: race condition with file being removed before repo update

    # Scenario: multiple copies and failures -- status should be failed and file removed on final failure

    # Scenario: umask is set correctly when running make (for yum repo)

    # Scenario: make is run properly (package should be added successfully)

    # Scenario: make fails once (package should be added successfully)

    # Scenario: make fails twice (package status should be set to failed, file removed)

    # Scenario: files are all removed from processing

    # Scenario: after failure, make sure can still add
