# Python pytest Example

This example shows direct Python SDK usage from the source tree. It generates both happy-path and negative registration data from `examples/contracts/register.tdf.json`.

From the repository root:

```bash
python -m pip install -e 'engine[dev]'
python -m pytest examples/frameworks/python-pytest
```
