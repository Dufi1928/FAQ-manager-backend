import pymysql

pymysql.install_as_MySQLdb()

# Monkey patch version to satisfy Django
try:
    import MySQLdb
    if MySQLdb.version_info < (2, 2, 1):
        MySQLdb.version_info = (2, 2, 1, 'final', 0)
except ImportError:
    pass

# Monkey patch Django to support MySQL 5.7
from django.db.backends.mysql.base import DatabaseWrapper
DatabaseWrapper.check_database_version_supported = lambda self: None
