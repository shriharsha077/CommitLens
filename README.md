# CommitLens

**Git Repository Intelligence and Code Churn Analyzer**

CommitLens reads a local Git repository and extracts useful information from
its commit history -- starting with basic commit data (hash, author, date,
message) and building toward deeper analysis like code churn and contributor
insights.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```python
from commitlens.scanner import scan_repo

commits = scan_repo("path/to/your/git/repo")
for c in commits:
    print(c["hash"], c["author"], c["date"], c["message"])
```

## Running Tests

```bash
pytest tests/ -v
```
