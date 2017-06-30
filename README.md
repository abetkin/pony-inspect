
##Instalation

Please install this package in editable mode and `git pull` frequently :)

```
pip install -e .
```

Currently requires Python 3, that will be fixed.

## Usage

The utility accepts path to `pony.orm.Database` object for `--database` argument.


For example if you have

```python
# app/db.py

db = Database(provider='postgres', **the_rest) 
```

Then run

```
python -m introspect --database app.db.db
```

There are some examples in the examples dir. To run them:

```
cd examples
python -m introspect --database=corporate_directory.db > out/corporate_directory.py
# or
python -m introspect --database=simple.db > out/simple.py
```