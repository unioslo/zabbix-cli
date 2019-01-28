import unittest

import zabbix_cli.config

try:
    # PY3
    import configparser
except ImportError:
    import ConfigParser as configparser


class MockConfig(configparser.ConfigParser, object):

    def __init__(self):
        super(MockConfig, self).__init__({'option_a': 'a', 'option_b': 'b'})
        self.add_section('foo')
        self.add_section('bar')


class TestOptionDescriptor(unittest.TestCase):

    class MockConfigWithDescriptors(MockConfig):
        foo_a = zabbix_cli.config.OptionDescriptor('foo', 'option_a')
        bar_b = zabbix_cli.config.OptionDescriptor('bar', 'option_b')

    def _make_config(self):
        return self.MockConfigWithDescriptors()

    def test_descriptor_cls(self):
        cls = self.MockConfigWithDescriptors
        desc = cls.foo_a
        self.assertTrue(isinstance(desc, zabbix_cli.config.OptionDescriptor))

    def test_descriptor_get(self):
        config = self._make_config()
        self.assertEqual(config.get('foo', 'option_a'),
                         getattr(config, 'foo_a'))

    def test_descriptor_set(self):
        config = self._make_config()
        config.foo_a = 'foo'
        self.assertEqual('foo', config.foo_a)
        self.assertEqual(config.get('foo', 'option_a'),
                         config.foo_a)

    def test_descriptor_del(self):
        config = self._make_config()
        config.foo_a = 'foo'
        del config.foo_a
        self.assertFalse('foo' == config.foo_a)
        self.assertEqual(config.get('foo', 'option_a'),
                         config.foo_a)


class TestOptionRegister(unittest.TestCase):

    def _make_register(self):
        return zabbix_cli.config.OptionRegister()

    def test_len(self):
        register = self._make_register()
        self.assertEqual(0, len(register))

        register.add('foo', 'bar')
        self.assertEqual(1, len(register))

        register.add('foo', 'baz')
        self.assertEqual(2, len(register))

    def test_iter(self):
        items = [('foo', 'bar'), ('foo', 'baz')]
        register = self._make_register()

        for section, option in items:
            register.add(section, option)

        for i, item in enumerate(register):
            self.assertEqual(items[i], item)

    def test_getitem(self):
        items = [('foo', 'bar'), ('foo', 'baz')]
        register = self._make_register()

        comparison = []
        for section, option in items:
            comparison.append(register.add(section, option))

        for i, item in enumerate(items):
            gotten = register[item]
            self.assertEqual(comparison[i], gotten)

    def test_sections(self):
        items = [('foo', 'bar'), ('foo', 'baz'), ('bar', 'foo')]
        expect = set(t[0] for t in items)
        register = self._make_register()

        for section, option in items:
            register.add(section, option)

        self.assertEqual(len(expect), len(register.sections))
        self.assertEqual(set(expect), set(register.sections))

    def test_initialize(self):
        items = [('foo', 'bar'), ('foo', 'baz'), ('bar', 'foo')]
        sections = set(t[0] for t in items)
        register = self._make_register()

        for section, option in items:
            register.add(section, option)

        config = configparser.ConfigParser()
        register.initialize(config)

        for section in sections:
            self.assertTrue(config.has_section(section))

        for section, option in items:
            self.assertTrue(config.has_option(section, option))
