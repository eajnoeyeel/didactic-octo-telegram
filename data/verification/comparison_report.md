# Description Optimizer 비교 검증 리포트

> 생성 시각: 스크립트 실행 시점
> 샘플 크기: 30 tools

## 1. 전체 요약

| Status | Count |
|--------|-------|
| gate_rejected | 13 |
| success | 17 |

**성공 건수:** 17
**평균 GEO 개선:** +0.1603
**최소 개선:** +0.0000
**최대 개선:** +0.3167

## 2. 차원별 Before/After 분석

| Dimension | Avg Before | Avg After | Avg Δ | Improved% |
|-----------|-----------|----------|-------|----------|
| clarity | 0.4882 | 0.6588 | +0.1706 | 59% |
| disambiguation | 0.0529 | 0.4588 | +0.4059 | 82% |
| parameter_coverage | 0.1324 | 0.2353 | +0.1029 | 35% |
| fluency | 0.6882 | 0.9618 | +0.2735 | 65% |
| stats | 0.0176 | 0.0176 | +0.0000 | 0% |
| precision | 0.1824 | 0.1912 | +0.0088 | 12% |

## 3. Tool별 Side-by-Side 비교

### Tool 1: `slack::SLACK_DELETE_A_COMMENT_ON_A_FILE`

**Status:** success
**GEO:** 0.1583 → 0.4000 (+0.2417)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.3500 | 0.7000 | +0.3500 |
| disambiguation | 0.0000 | 0.4000 | +0.4000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.4500 | 1.0000 | +0.5500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.1500 | 0.3000 | +0.1500 |

**Original:**
```
Deletes a specific comment from a file in Slack; this action is irreversible.
```

**Optimized:**
```
This tool allows users to delete a specific comment from a file in Slack, providing a straightforward way to manage feedback and discussions. Use this action when you need to remove irrelevant or inappropriate comments from your files. Please note that this deletion is irreversible, meaning once a comment is deleted, it cannot be recovered. This tool is specifically designed for managing comments within Slack files, ensuring clarity and organization in your collaborative workspace.
```

**Search Description:**
```
Delete comments from Slack files, irreversible comment removal, manage Slack file feedback, comment management tool for Slack, Slack file comment deletion, remove inappropriate comments in Slack, Slack collaboration tools.
```

---

### Tool 2: `EthanHenrickson/math-mcp::max`

**Status:** gate_rejected
**GEO:** 0.1250 → 0.4250

**Skip/Reject Reason:** Similarity: Semantic similarity 0.692 below threshold 0.75

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.4000 | 0.4000 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.1500 | 0.1500 | +0.0000 |
| fluency | 0.2000 | 0.2000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Finds the maximum value from a list of numbers
```

---

### Tool 3: `googlesuper::GOOGLESUPER_EVENTS_INSTANCES`

**Status:** gate_rejected
**GEO:** 0.0667 → 0.2667

**Skip/Reject Reason:** Similarity: Semantic similarity 0.638 below threshold 0.75

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.2000 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.2000 | 0.2000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Returns instances of the specified recurring event.
```

---

### Tool 4: `googlesuper::GOOGLESUPER_CREATE_DOCUMENT_MARKDOWN`

**Status:** success
**GEO:** 0.1500 → 0.3750 (+0.2250)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.3500 | 0.7500 | +0.4000 |
| disambiguation | 0.0000 | 0.5000 | +0.5000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.5500 | 1.0000 | +0.4500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Creates a new Google Docs document, optionally initializing it with a title and content provided as Markdown text.
```

**Optimized:**
```
This tool creates a new Google Docs document, allowing users to initialize it with a specified title and content formatted in Markdown text. It is particularly useful for users who want to quickly generate documents with structured content, making it ideal for note-taking, documentation, or any scenario where Markdown formatting enhances readability. Unlike other document creation tools, this tool specifically supports Markdown, ensuring that the formatting is preserved when the document is crea
```

**Search Description:**
```
Create Google Docs document with Markdown content, initialize with title. Ideal for note-taking and documentation. Supports Markdown formatting. Search queries: 'create Google Docs with Markdown', 'initialize Google Docs document', 'Markdown document creation tool'.
```

---

### Tool 5: `googlesuper::GOOGLESUPER_BATCH_ADD_MEDIA_ITEMS`

**Status:** gate_rejected
**GEO:** 0.1250 → 0.2917

**Skip/Reject Reason:** Similarity: Semantic similarity 0.743 below threshold 0.75

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.2000 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.5500 | 0.5500 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Adds one or more media items to an album in Google Photos.
```

---

### Tool 6: `slack::SLACK_LEAVE_A_CONVERSATION`

**Status:** success
**GEO:** 0.2000 → 0.3500 (+0.1500)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.4500 | +0.2500 |
| disambiguation | 0.0000 | 0.2000 | +0.2000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.7000 | 1.0000 | +0.3000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.3000 | 0.4500 | +0.1500 |

**Original:**
```
Leaves a Slack conversation given its channel ID; fails if leaving as the last member of a private channel or if used on a Slack Connect channel.
```

**Optimized:**
```
This tool allows users to leave a specific Slack conversation by providing the channel ID. It is important to note that this action will fail if the user is attempting to leave as the last member of a private channel or if the channel is a Slack Connect channel. Use this tool when you need to exit a conversation while ensuring you are not the last participant in a private setting. This tool is specifically designed for managing participation in Slack channels efficiently.
```

**Search Description:**
```
Leave a Slack conversation using channel ID. Fails if last member of private channel or Slack Connect channel. Manage Slack participation, exit conversations, Slack API tools, channel management.
```

---

### Tool 7: `slack::SLACK_ADD_AN_EMOJI_ALIAS_IN_SLACK`

**Status:** success
**GEO:** 0.1333 → 0.3167 (+0.1833)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.5500 | +0.3500 |
| disambiguation | 0.0000 | 0.2000 | +0.2000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.4500 | 1.0000 | +0.5500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.1500 | 0.1500 | +0.0000 |

**Original:**
```
Adds an alias for an existing custom emoji in a Slack Enterprise Grid organization.
```

**Optimized:**
```
Use this tool to add an alias for an existing custom emoji within a Slack Enterprise Grid organization. This functionality is specifically designed for teams looking to enhance their emoji usage by creating easy-to-remember aliases for custom emojis. It is particularly useful when you want to streamline communication and ensure that team members can quickly reference specific emojis without needing to remember their original names. This tool is ideal for organizations that utilize a variety of c
```

**Search Description:**
```
Add an alias for custom emoji in Slack Enterprise Grid. Enhance emoji communication, streamline usage, create easy-to-remember aliases. Ideal for teams with diverse custom emojis. Search queries: 'add emoji alias Slack', 'custom emoji management Slack', 'Slack Enterprise Grid emoji tools'.
```

---

### Tool 8: `gmail::GMAIL_ADD_LABEL_TO_EMAIL`

**Status:** success
**GEO:** 0.1833 → 0.3917 (+0.2083)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.7000 | +0.5000 |
| disambiguation | 0.0000 | 0.5000 | +0.5000 |
| parameter_coverage | 0.2000 | 0.2000 | +0.0000 |
| fluency | 0.7000 | 0.9500 | +0.2500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Adds and/or removes specified gmail labels for a message; ensure `message id` and all `label ids` are valid (use 'listlabels' for custom label ids).
```

**Optimized:**
```
The GMAIL_ADD_LABEL_TO_EMAIL tool allows users to add or remove specified Gmail labels from a message. This tool is particularly useful when you need to organize your emails by applying relevant labels. To use this tool effectively, ensure that you provide a valid `message id` along with all `label ids`. For custom label ids, utilize the 'listlabels' function to retrieve valid options. Unlike other email management tools, this tool specifically focuses on label management within Gmail, ensuring 
```

**Search Description:**
```
GMAIL_ADD_LABEL_TO_EMAIL, add Gmail labels, remove Gmail labels, manage email labels, valid message id, label ids, listlabels function, Gmail label management tool, email organization tool.
```

---

### Tool 9: `github::list_issue_types`

**Status:** gate_rejected
**GEO:** 0.1167 → 0.4250

**Skip/Reject Reason:** Similarity: Semantic similarity 0.739 below threshold 0.75

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.3500 | 0.3500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.1500 | 0.1500 | +0.0000 |
| fluency | 0.2000 | 0.2000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
List supported issue types for repository owner (organization).
```

---

### Tool 10: `EthanHenrickson/math-mcp::arccos`

**Status:** success
**GEO:** 0.0500 → 0.2667 (+0.2167)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.1000 | 0.4500 | +0.3500 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.0000 | 0.1500 | +0.1500 |
| fluency | 0.2000 | 1.0000 | +0.8000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Calculates the arccosine of a number in radians
```

**Optimized:**
```
Calculate the arccosine of a number in radians using this tool. This function is particularly useful when you need to determine the angle whose cosine is a given number, making it essential in various mathematical and engineering applications. Use this tool when working with trigonometric calculations, especially in contexts where radians are the preferred unit of measurement. It accepts a single numeric input representing the cosine value and returns the corresponding angle in radians.
```

**Search Description:**
```
arccosine calculator, compute arccos in radians, trigonometric functions tool, calculate angle from cosine, radians calculator, mathematical tool for arccos, find angle with cosine value
```

---

### Tool 11: `clay-inc/clay-mcp::merge_contacts`

**Status:** success
**GEO:** 0.2667 → 0.2917 (+0.0250)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.3500 | 0.2000 | -0.1500 |
| disambiguation | 0.3000 | 0.7000 | +0.4000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 0.9500 | 0.8500 | -0.1000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Merge all contact ids into one contact, this is a destructive action and can not be undone. Only run one contact group at a time and only with the users explicit permission.
```

**Optimized:**
```
Merge all contact IDs into a single contact record using the merge_contacts tool. This action is destructive and cannot be undone, so it is crucial to ensure that you have the user's explicit permission before proceeding. The tool is specifically designed to handle one contact group at a time, making it ideal for consolidating duplicate contacts efficiently. Unlike other tools that may allow non-destructive edits, this tool focuses solely on merging contacts, ensuring a streamlined process for m
```

**Search Description:**
```
Merge contacts tool, consolidate contact IDs, destructive action, user permission required, one contact group at a time, contact management, duplicate contacts, MCP tool for merging, efficient contact consolidation.
```

---

### Tool 12: `slack::SLACK_CREATE_CHANNEL_BASED_CONVERSATION`

**Status:** success
**GEO:** 0.2167 → 0.4333 (+0.2167)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.3500 | 0.8000 | +0.4500 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.3500 | 0.6500 | +0.3000 |
| fluency | 0.4500 | 1.0000 | +0.5500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.1500 | 0.1500 | +0.0000 |

**Original:**
```
Creates a new public or private Slack channel with a unique name; the channel can be org-wide, or team-specific if `team_id` is given (required if `org_wide` is false or not provided).
```

**Optimized:**
```
Create a new public or private Slack channel using the SLACK_CREATE_CHANNEL_BASED_CONVERSATION tool. This tool allows you to establish a channel with a unique name that can either be organization-wide or specific to a team. If you want the channel to be team-specific, you must provide the `team_id` parameter; this parameter is required when `org_wide` is set to false or is not provided. Use this tool when you need to facilitate communication within a specific group or across the entire organizat
```

**Search Description:**
```
Create Slack channel, public or private, unique name, team-specific, org-wide, requires team_id, Slack API, communication tool, establish channel, team collaboration, Slack integration.
```

---

### Tool 13: `TitanSneaker/paper-search-mcp-openai-v2::download_semantic`

**Status:** gate_rejected
**GEO:** 0.2250 → 0.3083

**Skip/Reject Reason:** InfoPreservation: Information lost from original: number '649', number '34', number '52', number '66281', number '98', number '884', number '09', number '38', number '10.18653', number '18', number '3011', number '2106.15928', number '112218234', number '12', number '3903', number '19872477', number '2323736', number '2106.15928', term 'https'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.2000 | 0.2000 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.4500 | 0.4500 | +0.0000 |
| fluency | 0.5000 | 0.5000 | +0.0000 |
| stats | 0.2000 | 0.2000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Download PDF of a Semantic Scholar paper.    

    Args:
        paper_id: Semantic Scholar paper ID, Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
           
```

---

### Tool 14: `Sallvainian/ngss-mcp::search_standards`

**Status:** success
**GEO:** 0.2500 → 0.4583 (+0.2083)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.4500 | 0.8500 | +0.4000 |
| disambiguation | 0.0000 | 0.5000 | +0.5000 |
| parameter_coverage | 0.3000 | 0.2500 | -0.0500 |
| fluency | 0.6000 | 1.0000 | +0.4000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.1500 | 0.1500 | +0.0000 |

**Original:**
```
Perform full-text search across all NGSS standard content including performance expectations, topics, and keywords (e.g., "energy transfer", "ecosystems", "chemical reactions", "climate change")
```

**Optimized:**
```
Utilize the Sallvainian/ngss-mcp::search_standards tool to perform a comprehensive full-text search across all Next Generation Science Standards (NGSS) content. This includes performance expectations, topics, and keywords such as 'energy transfer', 'ecosystems', 'chemical reactions', and 'climate change'. Ideal for educators and researchers seeking to locate specific standards or related information quickly. Unlike other search tools, this one is specifically designed for NGSS content, ensuring 
```

**Search Description:**
```
Full-text search tool for NGSS standards, including performance expectations and keywords. Ideal for educators. Search queries: 'NGSS standards search', 'energy transfer standards', 'ecosystems performance expectations', 'chemical reactions NGSS'.
```

---

### Tool 15: `github::create_or_update_file`

**Status:** success
**GEO:** 0.4083 → 0.4417 (+0.0333)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.6000 | -0.2500 |
| disambiguation | 0.0000 | 0.5000 | +0.5000 |
| parameter_coverage | 0.0000 | 0.1000 | +0.1000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.6000 | 0.4500 | -0.1500 |

**Original:**
```
Create or update a single file in a GitHub repository. 
If updating, you should provide the SHA of the file you want to update. Use this tool to create or update a file in a GitHub repository remotely; do not use it for local file operations.

In order to obtain the SHA of original file version before updating, use the following git command:
git ls-tree HEAD <path to file>

If the SHA is not provided, the tool will attempt to acquire it by fetching the current file contents from the repository, 
```

**Optimized:**
```
Create or update a single file in a GitHub repository using this tool. Unlike local file operations, this tool specifically handles remote file modifications. When updating a file, you must provide the SHA of the file you wish to update. To obtain the SHA of the original file version before updating, use the command: `git ls-tree HEAD <path to file>`. If the SHA is not supplied, the tool will attempt to fetch the current file contents from the repository, which may overwrite the latest committed
```

**Search Description:**
```
GitHub create or update file tool, update file SHA, remote file operations, manage GitHub repository files, git ls-tree command, overwrite committed changes, file version management in GitHub. Search queries: 'how to update a file in GitHub', 'GitHub file management tool', 'create or update file in 
```

---

### Tool 16: `Boysam2/aidroid::microsoft_docs_fetch`

**Status:** success
**GEO:** 0.3500 → 0.4500 (+0.1000)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.6000 | +0.6000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.1000 | 0.1000 | +0.0000 |
| precision | 0.1500 | 0.1500 | +0.0000 |

**Original:**
```
Fetch and convert a Microsoft Learn documentation page to markdown format. This tool retrieves the latest complete content of Microsoft documentation pages including Azure, .NET, Microsoft 365, and other Microsoft technologies.

## When to Use This Tool
- When search results provide incomplete information or truncated content
- When you need complete step-by-step procedures or tutorials
- When you need troubleshooting sections, prerequisites, or detailed explanations
- When search results refere
```

**Optimized:**
```
Fetch and convert a Microsoft Learn documentation page to markdown format. This tool retrieves the latest complete content of Microsoft documentation pages including Azure, .NET, Microsoft 365, and other Microsoft technologies. Unlike other tools that may provide only snippets, this tool ensures you receive the full context necessary for comprehensive understanding. It is specifically useful when search results yield incomplete information or truncated content. Use this tool after microsoft_docs
```

**Search Description:**
```
Microsoft Learn documentation fetch tool, convert Microsoft docs to markdown, complete Azure .NET Microsoft 365 content, retrieve full documentation, markdown format, troubleshooting guides, step-by-step tutorials, valid microsoft.com URLs.
```

---

### Tool 17: `clay-inc/clay-mcp::getRecentReminders`

**Status:** success
**GEO:** 0.3167 → 0.4833 (+0.1667)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.8000 | +0.8000 |
| parameter_coverage | 0.2000 | 0.2500 | +0.0500 |
| fluency | 0.8500 | 1.0000 | +0.1500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Use this tool to find recent reminders that have already occured. This tool is strictly prohibited from being used unless "reminder" or "reminders" are explicitly mentioned in the query.
```

**Optimized:**
```
Use this tool to find recent reminders that have already occurred. This tool is specifically designed for retrieving reminders, and it should only be utilized when the terms 'reminder' or 'reminders' are explicitly mentioned in the query. Unlike other tools that may provide general information, this tool focuses solely on past reminders, ensuring precise results. It accepts a `query` string to specify the reminder context, enhancing its effectiveness in delivering relevant outcomes. Please note 
```

**Search Description:**
```
Find recent reminders with clay-inc/clay-mcp::getRecentReminders. This tool retrieves past reminders based on specific queries containing 'reminder' or 'reminders'. Ideal for users needing precise reminder data, not future events. Search queries: 'get recent reminders', 'retrieve past reminders', 'c
```

---

### Tool 18: `googledrive::GOOGLEDRIVE_FILES_MODIFY_LABELS`

**Status:** success
**GEO:** 0.2917 → 0.4167 (+0.1250)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.6000 | 0.7500 | +0.1500 |
| disambiguation | 0.0000 | 0.6000 | +0.6000 |
| parameter_coverage | 0.1500 | 0.1500 | +0.0000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Modifies the set of labels applied to a file. returns a list of the labels that were added or modified. use when you need to programmatically change labels on a google drive file, such as adding, updating, or removing them.
```

**Optimized:**
```
The GOOGLEDRIVE_FILES_MODIFY_LABELS tool modifies the set of labels applied to a Google Drive file. It returns a list of the labels that were added or modified. This tool is specifically designed for programmatically changing labels on Google Drive files, allowing users to add, update, or remove labels as needed. Unlike other tools that may only provide read access, this tool focuses on label management, enabling efficient organization and categorization of files. It is ideal for users looking t
```

**Search Description:**
```
Modify labels on Google Drive files with GOOGLEDRIVE_FILES_MODIFY_LABELS. Programmatically add, update, or remove labels. Ideal for automating file organization. Search queries: 'modify Google Drive file labels', 'automate Google Drive labeling', 'update labels on Google Drive files'.
```

---

### Tool 19: `aryankeluskar/polymarket-mcp::get_trades`

**Status:** success
**GEO:** 0.2083 → 0.4917 (+0.2833)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.5000 | 0.5000 | +0.0000 |
| disambiguation | 0.0000 | 0.8000 | +0.8000 |
| parameter_coverage | 0.0000 | 0.5000 | +0.5000 |
| fluency | 0.6000 | 1.0000 | +0.4000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.1500 | 0.1500 | +0.0000 |

**Original:**
```
Get recent trade activity from Polymarket's Data API. Analyze trading patterns, volume, and market sentiment.
```

**Optimized:**
```
Get recent trade activity from Polymarket's Data API, specifically designed to provide insights into trading patterns, volume, and market sentiment. This tool allows users to analyze the latest trades, offering a comprehensive view of market dynamics. Unlike other trading analysis tools, it focuses exclusively on Polymarket's data, ensuring that users receive accurate and relevant information. The tool accepts parameters such as a `query` string to filter results and an optional `limit` integer 
```

**Search Description:**
```
Polymarket MCP get_trades tool for recent trade activity analysis. Analyze trading patterns, volume, market sentiment. Accepts query string and limit integer. Ideal for traders seeking real-time data insights.
```

---

### Tool 20: `googlecalendar::GOOGLECALENDAR_FIND_EVENT`

**Status:** success
**GEO:** 0.2250 → 0.5417 (+0.3167)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.5000 | 0.8500 | +0.3500 |
| disambiguation | 0.0000 | 0.5000 | +0.5000 |
| parameter_coverage | 0.2000 | 0.9000 | +0.7000 |
| fluency | 0.6500 | 1.0000 | +0.3500 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Finds events in a specified Google Calendar using text query, time ranges (event start/end, last modification), and event types; ensure `timeMin` is not chronologically after `timeMax` if both are provided.
```

**Optimized:**
```
The GOOGLECALENDAR_FIND_EVENT tool enables users to efficiently locate events within a specified Google Calendar. It employs a text query to search for events and allows for filtering based on time ranges, including event start and end times as well as last modification dates. It is crucial to ensure that the `timeMin` parameter is not chronologically after the `timeMax` parameter when both are provided. This tool is specifically designed for users needing to find events by various criteria, unl
```

**Search Description:**
```
Find events in Google Calendar using text queries and time ranges. Supports event start/end times and last modification dates. Ensure `timeMin` is before `timeMax`. Search for calendar events efficiently with GOOGLECALENDAR_FIND_EVENT tool.
```

---

### Tool 21: `ta-mcp/technical-analysis-mcp::market_screen`

**Status:** gate_rejected
**GEO:** 0.6417 → 0.2833

**Skip/Reject Reason:** GEO: GEO score decreased from 0.642 to 0.283; Similarity: Semantic similarity 0.749 below threshold 0.75; InfoPreservation: Information lost from original: number '1.', number '2.', number '3.', number '4.', number '5.', number '1.', number '2.', number '3.', number '4.', number '180', number '24', number '100', number '5.0', number '5%', number '0.05', number '0.15', number '15%', number '0.30', number '30%', number '2,900', number '30', number '2,900', number '500.', number '2,874', number '526', number '500 +', number '26', number '2,900', number '30', number '12,', number '15,', number '15', number '25', number '30', number '15', number '100', number '3.'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.9500 | 0.9500 | +0.0000 |
| disambiguation | 0.3000 | 0.3000 | +0.0000 |
| parameter_coverage | 1.0000 | 1.0000 | +0.0000 |
| fluency | 0.8000 | 0.8000 | +0.0000 |
| stats | 0.8000 | 0.8000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```

Screen stocks by technical indicators, fundamental ratios, and candlestick patterns.
Returns matching results with COMPLETE data (81 fields per stock).

*** YOU MUST USE THIS TOOL for ANY of these user queries: ***
- "multibagger stocks", "best stocks to buy", "stocks for long term"
- "undervalued stocks", "high growth stocks", "dividend stocks"
- "oversold stocks", "momentum stocks", "breakout candidates"
- "stocks to invest in", "good stocks", "quality stocks"
- "beaten down stocks", "turnaro
```

---

### Tool 22: `brave::brave_news_search`

**Status:** gate_rejected
**GEO:** 0.4750 → 0.5083

**Skip/Reject Reason:** InfoPreservation: Information lost from original: number '2025', number '06', number '27', number '20%', number '65910000'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.4500 | 0.4500 | +0.0000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.2500 | 0.2500 | +0.0000 |
| precision | 0.3000 | 0.3000 | +0.0000 |

**Original:**
```

    This tool searches for news articles using Brave's News Search API based on the user's query. Use it when you need current news information, breaking news updates, or articles about specific topics, events, or entities.
    
    When to use:
        - Finding recent news articles on specific topics
        - Getting breaking news updates
        - Researching current events or trending stories
        - Gathering news sources and headlines for analysis

    Returns a JSON list of news-relat
```

---

### Tool 23: `pi3ch/secdim::get_vulnerable_practice_labs`

**Status:** gate_rejected
**GEO:** 0.4750 → 0.4833

**Skip/Reject Reason:** InfoPreservation: Information lost from original: number '03', number '2021', number '15', number '30', number '16', number '35', number '20', number '30', number '36', number '70', number '30', number '60', number '71', number '100'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.1500 | 0.1500 | +0.0000 |
| fluency | 0.7500 | 0.7500 | +0.0000 |
| stats | 0.8000 | 0.8000 | +0.0000 |
| precision | 0.3000 | 0.3000 | +0.0000 |

**Original:**
```

    Return a list of hands-on SecDim secure coding labs related to a detected or suspected vulnerability.

    Use this tool to:
    - Find secure coding learning labs for specific vulnerabilities like XSS, SQL Injection, etc.
    - Explore OWASP Top 10 vulnerabilities and related labs
    - Provide additional resources and guides to help developers improve their secure coding skills

    Args:
        search: Search term for the vulnerability (e.g., 'xss', 'sql-injection', 'injection')
       
```

---

### Tool 24: `FaresYoussef94/aws-knowledge-mcp::aws___search_documentation`

**Status:** success
**GEO:** 0.5417 → 0.5417 (+0.0000)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.7500 | 0.7500 | +0.0000 |
| disambiguation | 0.2000 | 0.2000 | +0.0000 |
| parameter_coverage | 0.8500 | 0.8500 | +0.0000 |
| fluency | 0.5500 | 0.5500 | +0.0000 |
| stats | 0.2000 | 0.2000 | +0.0000 |
| precision | 0.7000 | 0.7000 | +0.0000 |

**Original:**
```
# AWS Documentation Search Tool
    This is your primary source for AWS information—always prefer this over general knowledge for AWS services, features, configurations, troubleshooting, and best practices.

    ## When to Use This Tool

    **Always search when the query involves:**
    - Any AWS service or feature (Lambda, S3, EC2, RDS, etc.)
    - AWS architecture, patterns, or best practices
    - AWS CLI, SDK, or API usage
    - AWS CDK or CloudFormation
    - AWS Amplify development
    - 
```

**Optimized:**
```
# AWS Documentation Search Tool
This is your primary source for AWS information—always prefer this over general knowledge for AWS services, features, configurations, troubleshooting, and best practices.

## When to Use This Tool
**Always search when the query involves:**
- Any AWS service or feature (Lambda, S3, EC2, RDS, etc.)
- AWS architecture, patterns, or best practices
- AWS CLI, SDK, or API usage
- AWS CDK or CloudFormation
- AWS Amplify development
- AWS errors or troubleshooting
- AWS p
```

**Search Description:**
```
AWS Documentation Search Tool for AWS services, features, configurations, troubleshooting, and best practices. Search for API methods, SDK code, CLI commands, new features, errors, debugging, Amplify apps, CDK concepts, and CloudFormation templates. Use specific queries for accurate results. Keyword
```

---

### Tool 25: `pi3ch/secdim::get_learning_pathway`

**Status:** gate_rejected
**GEO:** 0.4583 → 0.4250

**Skip/Reject Reason:** GEO: GEO score decreased from 0.458 to 0.425; InfoPreservation: Information lost from original: term 'API', term 'sql'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.4000 | 0.4000 | +0.0000 |
| fluency | 0.5500 | 0.5500 | +0.0000 |
| stats | 0.2500 | 0.2500 | +0.0000 |
| precision | 0.7000 | 0.7000 | +0.0000 |

**Original:**
```

    Return a personalized secure code learning pathway based on github or secdim profile context.

    Use this tool to:
    - Analyze GitHub profile to understand developer's experience and provide a personilized learning path
    - Analyze SecDim profile to understand developer's experience and provide a personilized learning path
    - Provide important resources and link to secure code learning labs on how to fix specific vulnerabilities
    - Teach developer how to patch a specific vulnera
```

---

### Tool 26: `clay-inc/clay-mcp::getNotes`

**Status:** gate_rejected
**GEO:** 0.4417 → 0.3917

**Skip/Reject Reason:** GEO: GEO score decreased from 0.442 to 0.392

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.5000 | 0.5000 | +0.0000 |
| parameter_coverage | 0.3000 | 0.3000 | +0.0000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.0000 | 0.0000 | +0.0000 |

**Original:**
```
Use ONLY when the user explicitly mentions "note" or "notes" to retrieve notes between two dates (e.g. "what notes from last week?"). Returns notes by creation date only - does NOT search note content or filter by other criteria. NEVER use this tool for finding contacts or any other purpose besides retrieving notes. This tool is strictly prohibited from being used unless "note" or "notes" are explicitly mentioned in the query.
```

---

### Tool 27: `brave::brave_local_search`

**Status:** success
**GEO:** 0.4750 → 0.5000 (+0.0250)

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.6000 | -0.2500 |
| disambiguation | 0.4000 | 0.8000 | +0.4000 |
| parameter_coverage | 0.0000 | 0.0000 | +0.0000 |
| fluency | 1.0000 | 1.0000 | +0.0000 |
| stats | 0.0000 | 0.0000 | +0.0000 |
| precision | 0.6000 | 0.6000 | +0.0000 |

**Original:**
```

    Brave Local Search API provides enrichments for location search results. Access to this API is available only through the Brave Search API Pro plans; confirm the user's plan before using this tool (if the user does not have a Pro plan, use the brave_web_search tool). Searches for local businesses and places using Brave's Local Search API. Best for queries related to physical locations, businesses, restaurants, services, etc.
    
    Returns detailed information including:
        - Busines
```

**Optimized:**
```
The Brave Local Search API provides enrichments for location search results, specifically tailored for queries related to physical locations, businesses, restaurants, services, and more. Access to this API is exclusively available through the Brave Search API Pro plans; confirm the user's plan before utilizing this tool. If the user does not have a Pro plan, please use the brave_web_search tool instead. This API returns detailed information including business names, addresses, ratings, review co
```

**Search Description:**
```
Brave Local Search API, location search, local businesses, restaurants, services, Pro plans, near me queries, business details, addresses, ratings, phone numbers, opening hours, fallback to brave_web_search. Ideal for searches like 'restaurants near me', 'businesses in San Francisco', 'local service
```

---

### Tool 28: `pi3ch/secdim::get_learning_pathway`

**Status:** gate_rejected
**GEO:** 0.4583 → 0.4333

**Skip/Reject Reason:** GEO: GEO score decreased from 0.458 to 0.433; InfoPreservation: Information lost from original: number '50+', term 'API', term 'sql'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.4000 | 0.4000 | +0.0000 |
| fluency | 0.5500 | 0.5500 | +0.0000 |
| stats | 0.2500 | 0.2500 | +0.0000 |
| precision | 0.7000 | 0.7000 | +0.0000 |

**Original:**
```

    Return a personalized secure code learning pathway based on github or secdim profile context.

    Use this tool to:
    - Analyze GitHub profile to understand developer's experience and provide a personilized learning path
    - Analyze SecDim profile to understand developer's experience and provide a personilized learning path
    - Provide important resources and link to secure code learning labs on how to fix specific vulnerabilities
    - Teach developer how to patch a specific vulnera
```

---

### Tool 29: `pi3ch/secdim::get_vulnerable_practice_labs`

**Status:** gate_rejected
**GEO:** 0.4750 → 0.4833

**Skip/Reject Reason:** InfoPreservation: Information lost from original: number '03', number '2021', number '15', number '30', number '16', number '35', number '20', number '30', number '36', number '70', number '30', number '60', number '71', number '100'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 0.8500 | 0.8500 | +0.0000 |
| disambiguation | 0.0000 | 0.0000 | +0.0000 |
| parameter_coverage | 0.1500 | 0.1500 | +0.0000 |
| fluency | 0.7500 | 0.7500 | +0.0000 |
| stats | 0.8000 | 0.8000 | +0.0000 |
| precision | 0.3000 | 0.3000 | +0.0000 |

**Original:**
```

    Return a list of hands-on SecDim secure coding labs related to a detected or suspected vulnerability.

    Use this tool to:
    - Find secure coding learning labs for specific vulnerabilities like XSS, SQL Injection, etc.
    - Explore OWASP Top 10 vulnerabilities and related labs
    - Provide additional resources and guides to help developers improve their secure coding skills

    Args:
        search: Search term for the vulnerability (e.g., 'xss', 'sql-injection', 'injection')
       
```

---

### Tool 30: `ta-mcp/technical-analysis-mcp::indicators_run_custom`

**Status:** gate_rejected
**GEO:** 0.5417 → 0.3833

**Skip/Reject Reason:** GEO: GEO score decreased from 0.542 to 0.383; InfoPreservation: Information lost from original: number '1.', number '2.', number '3.', number '4.', number '150+', number '1.', number '2.', number '3.', number '4.', number '1.', number '2.', number '3.', number '30', term 'API', term 'HTTP'

| Dimension | Before | After | Δ |
|-----------|--------|-------|---|
| clarity | 1.0000 | 1.0000 | +0.0000 |
| disambiguation | 0.3000 | 0.3000 | +0.0000 |
| parameter_coverage | 0.4500 | 0.4500 | +0.0000 |
| fluency | 0.8000 | 0.8000 | +0.0000 |
| stats | 0.2500 | 0.2500 | +0.0000 |
| precision | 0.4500 | 0.4500 | +0.0000 |

**Original:**
```

Compute a custom technical indicator by executing Python code against a
SINGLE ticker's OHLCV data. ALWAYS renders a professional multi-pane chart
with Bollinger Bands, RSI, and MACD included automatically.

┌──────────────────────────────────────────────────────────────────────┐
│  🔴 MANDATORY — READ BEFORE EVERY CALL                             │
│                                                                     │
│  1. ALWAYS pass plot_type='overlay' (or 'oscillator' for           │
│    
```

---

## 4. Quality Gate 분석

- **Gate Rejected:** 13 tools
- **Failed (optimizer error):** 0 tools

### Rejection Details

- `EthanHenrickson/math-mcp::max`: Similarity: Semantic similarity 0.692 below threshold 0.75
- `googlesuper::GOOGLESUPER_EVENTS_INSTANCES`: Similarity: Semantic similarity 0.638 below threshold 0.75
- `googlesuper::GOOGLESUPER_BATCH_ADD_MEDIA_ITEMS`: Similarity: Semantic similarity 0.743 below threshold 0.75
- `github::list_issue_types`: Similarity: Semantic similarity 0.739 below threshold 0.75
- `TitanSneaker/paper-search-mcp-openai-v2::download_semantic`: InfoPreservation: Information lost from original: number '649', number '34', number '52', number '66281', number '98', number '884', number '09', number '38', number '10.18653', number '18', number '3011', number '2106.15928', number '112218234', number '12', number '3903', number '19872477', number '2323736', number '2106.15928', term 'https'
- `ta-mcp/technical-analysis-mcp::market_screen`: GEO: GEO score decreased from 0.642 to 0.283; Similarity: Semantic similarity 0.749 below threshold 0.75; InfoPreservation: Information lost from original: number '1.', number '2.', number '3.', number '4.', number '5.', number '1.', number '2.', number '3.', number '4.', number '180', number '24', number '100', number '5.0', number '5%', number '0.05', number '0.15', number '15%', number '0.30', number '30%', number '2,900', number '30', number '2,900', number '500.', number '2,874', number '526', number '500 +', number '26', number '2,900', number '30', number '12,', number '15,', number '15', number '25', number '30', number '15', number '100', number '3.'
- `brave::brave_news_search`: InfoPreservation: Information lost from original: number '2025', number '06', number '27', number '20%', number '65910000'
- `pi3ch/secdim::get_vulnerable_practice_labs`: InfoPreservation: Information lost from original: number '03', number '2021', number '15', number '30', number '16', number '35', number '20', number '30', number '36', number '70', number '30', number '60', number '71', number '100'
- `pi3ch/secdim::get_learning_pathway`: GEO: GEO score decreased from 0.458 to 0.425; InfoPreservation: Information lost from original: term 'API', term 'sql'
- `clay-inc/clay-mcp::getNotes`: GEO: GEO score decreased from 0.442 to 0.392
- `pi3ch/secdim::get_learning_pathway`: GEO: GEO score decreased from 0.458 to 0.433; InfoPreservation: Information lost from original: number '50+', term 'API', term 'sql'
- `pi3ch/secdim::get_vulnerable_practice_labs`: InfoPreservation: Information lost from original: number '03', number '2021', number '15', number '30', number '16', number '35', number '20', number '30', number '36', number '70', number '30', number '60', number '71', number '100'
- `ta-mcp/technical-analysis-mcp::indicators_run_custom`: GEO: GEO score decreased from 0.542 to 0.383; InfoPreservation: Information lost from original: number '1.', number '2.', number '3.', number '4.', number '150+', number '1.', number '2.', number '3.', number '4.', number '1.', number '2.', number '3.', number '30', term 'API', term 'HTTP'

## 5. 검증 결론

아래 체크리스트를 사람이 직접 확인:

- [ ] 성공한 최적화의 GEO 개선이 양수인가?
- [ ] 6개 차원 중 최소 4개가 개선되었는가?
- [ ] 최적화된 설명이 원본의 의미를 보존하는가? (Section 3 side-by-side 확인)
- [ ] 최적화된 설명에 환각(hallucination)이 없는가?
- [ ] Quality Gate가 나쁜 최적화를 적절히 걸러냈는가?
- [ ] search_description이 벡터 검색에 적합한 키워드를 포함하는가?
- [ ] 최적화된 설명의 길이가 적절한가? (50-200 words)
