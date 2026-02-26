# Cerebral Python SDK

Python SDK for the Cerebral data versioning API.

## Quick Start

```python
import cerebral

repo = cerebral.repository('my-org/repo1')
print(repo.description)

with repo.session() as session:
    session.objects.put('foo/bar.csv', b'data')
    session.commit('update data')

for commit in repo.timeline():
    print(commit.message)
    for change in commit.diff():
        print(f'{change.path} was {change.status}')
```

See the [README](https://github.com/cerebral-storage/cerebral-python-sdk) for full documentation.
