
##Instalation

Please install this package in editable mode and `git pull` frequently :)

```
pip install -e .
```

Currently requires Python 3, that will be fixed.

## Usage

The utility accepts path to `pony.orm.Database` objrct for `--database` argument.


For example if you have

```python
# app/db.py

db = Database('sqlite', ':memory:')
```

Then run

```
python -m introspect --database app.db.db
```