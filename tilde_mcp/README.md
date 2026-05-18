# Tilde MCP Server

An MCP server that gives Claude direct access to [Tilde](https://tilde.run) — letting you manage repositories, import data from connectors, read and write files, run sandboxes, and track jobs, all through natural language.

## Setup

Install dependencies:
```bash
pip install "mcp[cli]>=1.0" tilde-sdk
```

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
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
- "Import images from Google Drive into training/bernard-v2/ using the gdrive connector"
- "Check the status of import job abc123"

### Read and write files
- "Update coordinator.py with this new version"
- "Create a notes file at runs/bernard-v1/notes.txt"
- "Delete the test folders we created earlier"

### Run commands in the repo
- "How much space are the checkpoints taking up?"
- "Find all .safetensors files in the repo"
- "Count the images in training/bernard-v1/"

### Launch and monitor sandboxes
- "Start a sandbox that runs the training pipeline"
- "What's the status of sandbox xyz?"

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
