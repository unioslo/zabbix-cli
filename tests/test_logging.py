import logging
import unittest

import zabbix_cli.logs


logger = logging.getLogger(__name__)


class CollectHandler(logging.Handler):

    def __init__(self):
        super(CollectHandler, self).__init__(logging.NOTSET)
        self.records = []

    def emit(self, record):
        print('emit', repr(record))
        self.records.append(record)


class TestSafeFormatting(unittest.TestCase):

    def _make_log_record(self, msg, *args):
        # locals for readability
        record_logger = 'example-logger-name'
        record_level = logging.ERROR
        record_pathname = __file__
        record_lineno = 1
        record_exc_info = None
        return logging.LogRecord(record_logger, record_level, record_pathname,
                                 record_lineno, msg, args, record_exc_info)

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
        msg = "foo",
        args = (1, 2)
        record = self._make_safe_record(msg, *args)
        self.assertEqual(msg, record.msg)
        self.assertEqual(args, record.args)

    def test_safe_record_missing_dict(self):
        fmt = "%(msg)s-%(this_probably_does_not_exist)s"
        record = self._make_safe_record("foo")
        expect = "foo-%s" % (None, )
        result = fmt % record.__dict__
        self.assertEqual(expect, result)

    def test_safe_formatter(self):
        fmt = "%(name)s - %(something)s - %(msg)s"
        formatter = zabbix_cli.logs.SafeFormatter(fmt)
        record = self._make_log_record("foo")

        expect = fmt % {'name': record.name,
                        'something': None,
                        'msg': record.msg}
        self.assertEqual(expect, formatter.format(record))


class TestLoggingContext(unittest.TestCase):

    def _get_log_record(self):
        return type('mock_LogRecord', (object, ), {})()

    def _get_logger(self, test_name):
        handler = CollectHandler()
        test_logger = logger.getChild(test_name)
        test_logger.addHandler(handler)
        test_logger.propagate = False
        test_logger.disabled = False
        test_logger.setLevel(logging.NOTSET + 1)
        return test_logger, handler.records

    def test_context_filter_returns_true(self):
        f = zabbix_cli.logs.ContextFilter('foo', 'bar')
        r = self._get_log_record()
        self.assertTrue(f.filter(r))

    def test_context_filter_sets_field(self):
        f = zabbix_cli.logs.ContextFilter('foo', 'bar')
        r = self._get_log_record()
        f.filter(r)
        self.assertEqual('bar', r.foo)

    def test_context_filter_resets_field(self):
        f1 = zabbix_cli.logs.ContextFilter('foo', 'bar')
        f2 = zabbix_cli.logs.ContextFilter('foo', 'baz')
        r = self._get_log_record()
        f1.filter(r)
        f2.filter(r)
        self.assertEqual('baz', r.foo)

    def test_log_context_no_context(self):
        test_logger, records = self._get_logger('test_log_context_no_context')
        fmt = "%(no_field)s"
        formatter = zabbix_cli.logs.SafeFormatter(fmt)
        test_logger.info("foo")
        self.assertEqual(1, len(records))
        self.assertEqual(fmt % {'no_field': None},
                         formatter.format(records[0]))

    def test_log_context(self):
        test_logger, records = self._get_logger('test_log_context')
        fmt = "%(no_field)s"
        formatter = zabbix_cli.logs.SafeFormatter(fmt)
        with zabbix_cli.logs.LogContext(test_logger, no_field='foo'):
            test_logger.info("foo")
        self.assertEqual(1, len(records))
        self.assertEqual("foo", formatter.format(records[0]))

    def test_log_context_nested(self):
        test_logger, records = self._get_logger('test_log_context_nested')
        fmt = "%(no_field)s"
        formatter = zabbix_cli.logs.SafeFormatter(fmt)
        with zabbix_cli.logs.LogContext(test_logger, no_field='foo'):
            with zabbix_cli.logs.LogContext(test_logger, no_field='bar'):
                test_logger.info("nested")
            test_logger.info("first")
        test_logger.info("no context")

        self.assertEqual(3, len(records))
        # first record was nested in two LogContexts
        self.assertEqual("bar", formatter.format(records[0]))
        # second record was nested in one LogContext
        self.assertEqual("foo", formatter.format(records[1]))
        # last record was logged after contexts
        self.assertEqual(fmt % {'no_field': None},
                         formatter.format(records[2]))
