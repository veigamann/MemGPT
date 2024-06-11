__version__ = "0.3.17"
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from memgpt.client.admin import Admin
from memgpt.client.client import create_client
