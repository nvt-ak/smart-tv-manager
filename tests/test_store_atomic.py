"""Atomic device-store writes must work when PATH is on a different filesystem."""
import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import store


class AtomicStoreTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.target = Path(self.root.name) / 'target' / 'devices.json'
        self.key_dir = Path(self.root.name) / 'other-filesystem'
        self.key_dir.mkdir()
        self.target.parent.mkdir()
        for name, value in [('PATH', str(self.target)), ('KEY_DIR', str(self.key_dir))]:
            patch = mock.patch.object(store, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_replace_uses_destination_directory_even_when_key_dir_differs(self):
        real_replace = os.replace
        def same_filesystem_replace(source, destination):
            if Path(source).parent.resolve() != Path(destination).parent.resolve():
                raise OSError(errno.EXDEV, 'Invalid cross-device link')
            return real_replace(source, destination)
        with mock.patch.object(store.os, 'replace', side_effect=same_filesystem_replace):
            store.save([{'host': 'example.invalid', 'name': 'Fixture'}])
        self.assertEqual(store.load()[0]['name'], 'Fixture')
        self.assertEqual(list(self.key_dir.iterdir()), [])

    def test_missing_destination_parent_is_created(self):
        nested = self.target.parent / 'nested' / 'devices.json'
        with mock.patch.object(store, 'PATH', str(nested)):
            store.save([])
        self.assertEqual(json.loads(nested.read_text()), [])

    def test_failed_replace_preserves_previous_file_and_cleans_temporary_file(self):
        self.target.write_text('[{"host":"previous.invalid"}]')
        with mock.patch.object(store.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                store.save([{'host': 'new.invalid'}])
        self.assertEqual(json.loads(self.target.read_text()), [{'host': 'previous.invalid'}])
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])
        self.assertEqual(list(self.key_dir.iterdir()), [])
