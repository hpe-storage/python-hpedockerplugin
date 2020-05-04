## Contributions

This section describes steps that should be done when creating contributions for this plugin.

#### Running plugin unit tests

All contributions to the plugin must pass all unit and PEP8 tests.

Run the following commands to run the plugin unit tests:

```
cd test
sudo trial test_hpe_plugin.py
```

Use the following command to check for PEP8 violations in the plugin:

```
tox
```
