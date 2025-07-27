Please respond in {language}.

Analyze the commit history and generate proposals to squash logically related commits.

## Commit History:
{log_output}

## Details:
{details_text}

## Analysis Criteria:
- Consecutive small modifications to the same file
- Typo fixes and their corrections
- Feature additions and their tests
- Meaningless messages like "fix", "wip", "tmp"
- Logically unified changes dispersed across commits

Output proposals in the following JSON format:

{{
  "proposals": [
    {{
      "source_commits": ["commit-id1", "commit-id2"],
      "target_commit": "commit-id1",
      "reason": "Reason for squashing",
      "suggested_message": "Proposed commit message"
    }}
  ]
}}

Return empty array if no proposals. Output only JSON format: