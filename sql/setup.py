# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['snsql',
 'snsql._ast',
 'snsql._ast.expressions',
 'snsql.reader',
 'snsql.sql',
 'snsql.sql._mechanisms',
 'snsql.sql.parser',
 'snsql.sql.reader',
 'snsql.xpath',
 'snsql.xpath.parser']

package_data = \
{'': ['*']}

install_requires = \
['PyYAML>=5.4.1,<6.0.0',
 'antlr4-python3-runtime==4.9.3',
 'graphviz>=0.17,<0.18',
 'opendp>=0.6.0,<0.7.0',
 'pandasql>=0.7.3,<0.8.0']

setup_kwargs = {
    'name': 'smartnoise-sql',
    'version': '0.2.8',
    'description': 'Differentially Private SQL Queries',
    'long_description': '[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python](https://img.shields.io/badge/python-3.7%20%7C%203.8-blue)](https://www.python.org/)\n\n<a href="https://smartnoise.org"><img src="https://github.com/opendp/smartnoise-sdk/raw/main/images/SmartNoise/SVG/Logo%20Mark_grey.svg" align="left" height="65" vspace="8" hspace="18"></a>\n\n## SmartNoise SQL\n\nDifferentially private SQL queries.  Tested with:\n* PostgreSQL\n* SQL Server\n* Spark\n* Pandas (SQLite)\n* PrestoDB\n* BigQuery\n\nSmartNoise is intended for scenarios where the analyst is trusted by the data owner.  SmartNoise uses the [OpenDP](https://github.com/opendp/opendp) library of differential privacy algorithms.\n\n## Installation\n\n```\npip install smartnoise-sql\n```\n\n## Querying a Pandas DataFrame\n\nUse the `from_df` method to create a private reader that can issue queries against a pandas dataframe.\n\n```python\nimport snsql\nfrom snsql import Privacy\nimport pandas as pd\nprivacy = Privacy(epsilon=1.0, delta=0.01)\n\ncsv_path = \'PUMS.csv\'\nmeta_path = \'PUMS.yaml\'\n\npums = pd.read_csv(csv_path)\nreader = snsql.from_df(pums, privacy=privacy, metadata=meta_path)\n\nresult = reader.execute(\'SELECT sex, AVG(age) AS age FROM PUMS.PUMS GROUP BY sex\')\n```\n\n## Querying a SQL Database\n\nUse `from_connection` to wrap an existing database connection.\n\n```python\nimport snsql\nfrom snsql import Privacy\nimport psycopg2\n\nprivacy = Privacy(epsilon=1.0, delta=0.01)\nmeta_path = \'PUMS.yaml\'\n\npumsdb = psycopg2.connect(user=\'postgres\', host=\'localhost\', database=\'PUMS\')\nreader = snsql.from_connection(pumsdb, privacy=privacy, metadata=meta_path)\n\nresult = reader.execute(\'SELECT sex, AVG(age) AS age FROM PUMS.PUMS GROUP BY sex\')\n```\n\n## Querying a Spark DataFrame\n\nUse `from_connection` to wrap a spark session.\n\n```python\nimport pyspark\nfrom pyspark.sql import SparkSession\nspark = SparkSession.builder.getOrCreate()\nfrom snsql import *\n\npums = spark.read.load(...)  # load a Spark DataFrame\npums.createOrReplaceTempView("PUMS_large")\n\nmetadata = \'PUMS_large.yaml\'\n\nprivate_reader = from_connection(\n    spark, \n    metadata=metadata, \n    privacy=Privacy(epsilon=3.0, delta=1/1_000_000)\n)\nprivate_reader.reader.compare.search_path = ["PUMS"]\n\n\nres = private_reader.execute(\'SELECT COUNT(*) FROM PUMS_large\')\nres.show()\n```\n\n## Privacy Cost\n\nThe privacy parameters epsilon and delta are passed in to the private connection at instantiation time, and apply to each computed column during the life of the session.  Privacy cost accrues indefinitely as new queries are executed, with the total accumulated privacy cost being available via the `spent` property of the connection\'s `odometer`:\n\n```python\nprivacy = Privacy(epsilon=0.1, delta=10e-7)\n\nreader = from_connection(conn, metadata=metadata, privacy=privacy)\nprint(reader.odometer.spent)  # (0.0, 0.0)\n\nresult = reader.execute(\'SELECT COUNT(*) FROM PUMS.PUMS\')\nprint(reader.odometer.spent)  # approximately (0.1, 10e-7)\n```\n\nThe privacy cost increases with the number of columns:\n\n```python\nreader = from_connection(conn, metadata=metadata, privacy=privacy)\nprint(reader.odometer.spent)  # (0.0, 0.0)\n\nresult = reader.execute(\'SELECT AVG(age), AVG(income) FROM PUMS.PUMS\')\nprint(reader.odometer.spent)  # approximately (0.4, 10e-6)\n```\n\nThe odometer is advanced immediately before the differentially private query result is returned to the caller.  If the caller wishes to estimate the privacy cost of a query without running it, `get_privacy_cost` can be used:\n\n```python\nreader = from_connection(conn, metadata=metadata, privacy=privacy)\nprint(reader.odometer.spent)  # (0.0, 0.0)\n\ncost = reader.get_privacy_cost(\'SELECT AVG(age), AVG(income) FROM PUMS.PUMS\')\nprint(cost)  # approximately (0.4, 10e-6)\n\nprint(reader.odometer.spent)  # (0.0, 0.0)\n```\n\nNote that the total privacy cost of a session accrues at a slower rate than the sum of the individual query costs obtained by `get_privacy_cost`.  The odometer accrues all invocations of mechanisms for the life of a session, and uses them to compute total spend.\n\n```python\nreader = from_connection(conn, metadata=metadata, privacy=privacy)\nquery = \'SELECT COUNT(*) FROM PUMS.PUMS\'\nepsilon_single, _ = reader.get_privacy_cost(query)\nprint(epsilon_single)  # 0.1\n\n# no queries executed yet\nprint(reader.odometer.spent)  # (0.0, 0.0)\n\nfor _ in range(100):\n    reader.execute(query)\n\nepsilon_many, _ = reader.odometer.spent\nprint(f\'{epsilon_many} < {epsilon_single * 100}\')\n```\n\n## Histograms\n\nSQL `group by` queries represent histograms binned by grouping key.  Queries over a grouping key with unbounded or non-public dimensions expose privacy risk. For example:\n\n```sql\nSELECT last_name, COUNT(*) FROM Sales GROUP BY last_name\n```\n\nIn the above query, if someone with a distinctive last name is included in the database, that person\'s record might accidentally be revealed, even if the noisy count returns 0 or negative.  To prevent this from happening, the system will automatically censor dimensions which would violate differential privacy.\n\n## Private Synopsis\n\nA private synopsis is a pre-computed set of differentially private aggregates that can be filtered and aggregated in various ways to produce new reports.  Because the private synopsis is differentially private, reports generated from the synopsis do not need to have additional privacy applied, and the synopsis can be distributed without risk of additional privacy loss.  Reports over the synopsis can be generated with non-private SQL, within an Excel Pivot Table, or through other common reporting tools.\n\nYou can see a sample [notebook for creating private synopsis](samples/Synopsis.ipynb) suitable for consumption in Excel or SQL.\n\n## Limitations\n\nYou can think of the data access layer as simple middleware that allows composition of `opendp` computations using the SQL language.  The SQL language provides a limited subset of what can be expressed through the full `opendp` library.  For example, the SQL language does not provide a way to set per-field privacy budget.\n\nBecause we delegate the computation of exact aggregates to the underlying database engines, execution through the SQL layer can be considerably faster, particularly with database engines optimized for precomputed aggregates.  However, this design choice means that analysis graphs composed with SQL language do not access data in the engine on a per-row basis.  Therefore, SQL queries do not currently support algorithms that require per-row access, such as quantile algorithms that use underlying values.  This is a limitation that future releases will relax for database engines that support row-based access, such as Spark.\n\nThe SQL processing layer has limited support for bounding contributions when individuals can appear more than once in the data.  This includes ability to perform reservoir sampling to bound contributions of an individual, and to scale the sensitivity parameter.  These parameters are important when querying reporting tables that might be produced from subqueries and joins, but require caution to use safely.\n\nFor this release, we recommend using the SQL functionality while bounding user contribution to 1 row.  The platform defaults to this option by setting `max_contrib` to 1, and should only be overridden if you know what you are doing.  Future releases will focus on making these options easier for non-experts to use safely.\n\n\n## Communication\n\n- You are encouraged to join us on [GitHub Discussions](https://github.com/opendp/opendp/discussions/categories/smartnoise)\n- Please use [GitHub Issues](https://github.com/opendp/smartnoise-sdk/issues) for bug reports and feature requests.\n- For other requests, including security issues, please contact us at [smartnoise@opendp.org](mailto:smartnoise@opendp.org).\n\n## Releases and Contributing\n\nPlease let us know if you encounter a bug by [creating an issue](https://github.com/opendp/smartnoise-sdk/issues).\n\nWe appreciate all contributions. Please review the [contributors guide](../contributing.rst). We welcome pull requests with bug-fixes without prior discussion.\n\nIf you plan to contribute new features, utility functions or extensions, please first open an issue and discuss the feature with us.\n',
    'author': 'SmartNoise Team',
    'author_email': 'smartnoise@opendp.org',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://smartnoise.org',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>3.6,<3.11',
}


setup(**setup_kwargs)
