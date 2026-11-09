Feature: Recording decisions and notes with loopspec state add
  The command appends one line to the right section of state.md,
  keeps every other byte, and tells the caller who decided.

  Background:
    Given an approved plan in an isolated project

  Scenario: A human decision names who decided
    When the user records a decision by "HUMAN" named "张 三"
    Then the Change state lists that decision tagged "[HUMAN: 张 三]"

  Scenario: A model decision names the Agent role
    When the user records a decision by "MODEL" named "后端 Agent"
    Then the Change state lists that decision tagged "[MODEL: 后端 Agent]"

  Scenario: An open question needs an explicit scope
    When an open question is added without a scope
    Then the command fails with "workflow_invalid"
    And no state file changed
    When an open question is added with scope "change"
    Then it appears in the Change state only
    When an open question is added with scope "plan"
    Then it appears in the Plan state only
    And the entry has no node tag

  Scenario: A plan-level open question may name a node
    When an open question is added with scope "plan" and node "requirements/proposal"
    Then the entry carries the node tag "[requirements/proposal]"

  Scenario: A correction is appended and the original stays
    Given a recorded note "第一版"
    When a correcting note is added
    Then both notes are present in order

  Scenario: Line endings of untouched text survive a CRLF file
    Given the Change state uses CRLF line endings
    When a reference is recorded
    Then every line ending in the file is still CRLF
    And the text around the target section is byte-identical

  Scenario: A busy lock is reported and a retry succeeds
    Given another command holds the Change write lock
    When a note is added
    Then the command fails with "concurrent_write"
    And no state file changed
    When the lock is released and the same command is retried
    Then the note is recorded

  Scenario: Rework rounds count per Gate
    When a rework note is attempted for "qa/test"
    Then the command fails with "state_rework_no_rollback"
    And no state file changed
    When the "qa/test" Gate fails and is rolled back
    And a rework note is recorded for "qa/test"
    And the "qa/test" Gate fails and is rolled back
    And a rework note is recorded for "qa/test"
    Then the first rework note reads "attempt 1" with its rollback number
    And the second rework note reads "attempt 2" with its rollback number

  @subprocess
  Scenario: The installed command line records a decision
    When the installed "loopspec" executable records a decision
    Then it exits with status 0 and the line is in the Change state
