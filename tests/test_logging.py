from __future__ import annotations

import logging
import unittest

import zabbix_cli.logs

logger = logging.getLogger(__name__)


class CollectHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.NOTSET)
        self.records = []

    def emit(self, record):
        print("emit", repr(record))
        self.records.append(record)


class TestSafeFormatting(unittest.TestCase):
    def _make_log_record(self, msg, *args):
        # locals for readability
        record_logger = "example-logger-name"
        record_level = logging.ERROR
        record_pathname = __file__
        record_lineno = 1
        record_exc_info = None
        return logging.LogRecord(
            record_logger,
            record_level,
            record_pathname,
            record_lineno,
            msg,
            args,
            record_exc_info,
        )

    def _make_safe_record(self, msg, *args):
        return zabbix_cli.logs.SafeRecord(self._make_log_record(msg, *args))

    def test_safe_record(self):
        self._make_safe_record("foo")
        self.assertTrue(True)  # reached

    def test_safe_record_basic_message(self):
        message = "foo"
        record = self._make_safe_record(message)
        self.assertEqual(message, record.getMessage())

    def test_safe_record_formatted_message(self):
        expect = "foo 01 02"
        record = self._make_safe_record("foo %02d %02d", 1, 2)
        self.assertEqual(expect, record.getMessage())

    def test_safe_record_attr(self):
        msg = ("foo",)
        args = (1, 2)
        record = self._make_safe_record(msg, *args)
        self.assertEqual(msg, record.msg)
        self.assertEqual(args, record.args)

    def test_safe_record_missing_dict(self):
        fmt = "%(msg)s-%(this_probably_does_not_exist)s"
        record = self._make_safe_record("foo")
        expect = f"foo-{None}"
        result = fmt % record.__dict__
        self.assertEqual(expect, result)

    def test_safe_formatter(self):
        fmt = "%(name)s - %(something)s - %(msg)s"
        formatter = zabbix_cli.logs.SafeFormatter(fmt)
        record = self._make_log_record("foo")

        expect = fmt % {"name": record.name, "something": None, "msg": record.msg}
        self.assertEqual(expect, formatter.format(record))
