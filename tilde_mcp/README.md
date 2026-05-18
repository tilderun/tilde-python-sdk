# Tilde MCP Server

An MCP server that gives Claude direct access to [Tilde](https://tilde.run) — letting you manage repositories, import data from connectors, read and write files, run sandboxes, and track jobs, all through natural language.

## Setup

Install dependencies:
```bash
pip install "mcp[cli]>=1.0" tilde-sdk
```

Add to `.claude/settings.json` in your project:
```json
{
  "mcpServers": {
    "tilde": {
      "command": "python3",
      "args": ["/path/to/tilde_mcp/server.py"],
      "env": {
        "TILDE_API_KEY": "tak-..."
      }
    }
  }
}
```

## What you can do

### Explore repositories
- "What files are in the checkpoints folder?"
- "Show me the contents of coordinator.py"
- "What connectors does my org have?"

### Import data from external sources
- "Import images from Google Drive into training/my-subject-v2/ using the gdrive connector"
- "Check the status of import job abc123"

### Read and write files
- "Update coordinator.py with this new version"
- "Create a notes file at runs/my-subject-v1/notes.txt"
- "Delete the test folders we created earlier"

### Run commands in the repo
- "How much space are the checkpoints taking up?"
- "Find all .safetensors files in the repo"
- "Count the images in training/my-subject-v1/"

### Launch and monitor sandboxes
- "Start a sandbox that runs the training pipeline"
- "What's the status of sandbox xyz?"

## Example: Import data and verify it landed

The following shows a multi-step workflow — import training images from a Google Drive connector, poll until complete, inspect the result, and count the files:

```
Step 1: list_connectors
  gdrive-images  id=0718ef79-...

Step 2: import_from_connector → training/my-subject-v3/
  job_id=fc93d0dc-...  status=running

Step 3: polling...
  running  objects=103
  completed  objects=207
  final: completed  error: none

Step 4: list_objects (prefix=training/my-subject-v3/)
  training/my-subject-v3/IMG_0001.jpg  (706450 bytes)
  training/my-subject-v3/IMG_0001.txt  (128 bytes)
  training/my-subject-v3/IMG_0002.jpg  (2147924 bytes)
  training/my-subject-v3/IMG_0002.txt  (112 bytes)
  ...

Step 5: exec_sandbox — find /sandbox/training/my-subject-v3 | wc -l
  file count: 220  exit_code=0

Step 6: list_objects (prefix=checkpoints/my-subject-v3/)
  checkpoints/my-subject-v3/model_step-0500.safetensors  (786432000 bytes)
  checkpoints/my-subject-v3/model_step-1000.safetensors  (786432000 bytes)
  checkpoints/my-subject-v3/train.log  (24312 bytes)
```

All from a single prompt to Claude: *"Import my Google Drive images into training/my-subject-v3/ and tell me how many files landed."*

## Tools

| Tool | Description |
|---|---|
| `list_repos(org)` | List repositories in an org |
| `list_connectors(org)` | List connectors in an org |
| `list_objects(repo, prefix?, limit?)` | List files at HEAD |
| `read_object(repo, path)` | Read file content |
| `write_objects(repo, files, message)` | Write files and commit |
| `delete_objects(repo, paths, message)` | Delete files and commit |
| `list_commits(repo, amount?)` | List recent commits* |
| `get_commit(repo, commit_id)` | Get commit details* |
| `commit_diff(repo, commit_id, prefix?)` | Show what changed in a commit* |
| `revert_commit(repo, commit_id, message?)` | Revert to a previous commit* |
| `import_from_connector(repo, connector_id, destination_path, source_prefix?)` | Start a connector import job |
| `get_import_job(repo, job_id)` | Poll import job status |
| `exec_sandbox(repo, command, image?, env?, timeout_seconds?)` | Run a command, return stdout |
| `create_sandbox(repo, image, command?, env?, timeout_seconds?)` | Launch a detached sandbox |
| `get_sandbox_status(repo, sandbox_id)` | Check sandbox state |

\* requires a user key — agent keys (`tak-...`) return 403 on commit log endpoints
