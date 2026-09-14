import shutil
import tempfile
import unittest
import json
import zipfile
import sqlite3
from unittest.mock import patch
from pathlib import Path

from pzrevize.database import Database
from pzrevize.nas_sync import (
    NasConflictError, NasSyncError, compare_database_states, database_logical_signature,
    pull_from_nas, push_to_nas, safe_sync_once, set_setting, _sha256,
)


class NasSyncSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pzsync_test_'))
        self.base = self.tmp / 'base.db'
        self.db = Database(self.base)
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)", ('R-001','ELEKTRO','Base'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, name):
        dest = self.tmp / name
        self.db.export_database(dest)
        return dest

    def test_local_extra_revision_is_local_superset(self):
        remote = self.copy('remote.db')
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)", ('R-002','ELEKTRO','Offline navíc'))
        cmp = compare_database_states(self.base, remote)
        self.assertEqual(cmp['relation'], 'local_superset')
        self.assertEqual(cmp['local_only_revisions'], ['R-002'])

    def test_remote_extra_revision_is_remote_superset(self):
        local = self.copy('local.db')
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)", ('R-002','STROJ','NAS navíc'))
        cmp = compare_database_states(local, self.base)
        self.assertEqual(cmp['relation'], 'remote_superset')
        self.assertEqual(cmp['remote_only_revisions'], ['R-002'])

    def test_changed_same_revision_is_conflict(self):
        remote = self.copy('remote_changed.db')
        self.db.execute("UPDATE revisions SET subject=? WHERE revision_no=?", ('Lokální změna','R-001'))
        rdb = Database(remote)
        rdb.execute("UPDATE revisions SET subject=? WHERE revision_no=?", ('NAS změna','R-001'))
        cmp = compare_database_states(self.base, remote)
        self.assertEqual(cmp['relation'], 'conflict')
        self.assertEqual(cmp['changed_revisions'], ['R-001'])


    def test_safe_sync_pushes_local_superset_without_pull(self):
        set_setting(self.db, 'nas_generation', '4')
        comparison = {'relation':'local_superset','generation':7,'local_only_revisions':['R-002'],'remote_only_revisions':[],'changed_revisions':[]}
        with patch('pzrevize.nas_sync.get_status', return_value={'generation':7}), \
             patch('pzrevize.nas_sync.compare_with_nas', return_value=comparison), \
             patch('pzrevize.nas_sync.push_to_nas', return_value={'generation':8}) as push, \
             patch('pzrevize.nas_sync.pull_from_nas') as pull:
            result = safe_sync_once(self.db, 'http://nas', 'token', 'test')
        self.assertEqual(result['action'], 'push')
        push.assert_called_once()
        self.assertEqual(push.call_args.kwargs['expected_generation'], 7)
        pull.assert_not_called()

    def test_safe_sync_defers_remote_pull_with_open_editor(self):
        set_setting(self.db, 'nas_generation', '4')
        comparison = {'relation':'remote_superset','generation':7,'local_only_revisions':[],'remote_only_revisions':['R-002'],'changed_revisions':[]}
        with patch('pzrevize.nas_sync.get_status', return_value={'generation':7}), \
             patch('pzrevize.nas_sync.compare_with_nas', return_value=comparison), \
             patch('pzrevize.nas_sync.pull_from_nas') as pull:
            result = safe_sync_once(self.db, 'http://nas', 'token', 'test', allow_pull=False)
        self.assertEqual(result['action'], 'deferred_pull')
        pull.assert_not_called()

    def test_safe_sync_conflict_never_overwrites(self):
        set_setting(self.db, 'nas_generation', '4')
        comparison = {'relation':'conflict','generation':7,'local_only_revisions':['R-LOCAL'],'remote_only_revisions':['R-NAS'],'changed_revisions':['R-001']}
        with patch('pzrevize.nas_sync.get_status', return_value={'generation':7}), \
             patch('pzrevize.nas_sync.compare_with_nas', return_value=comparison), \
             patch('pzrevize.nas_sync.push_to_nas') as push, \
             patch('pzrevize.nas_sync.pull_from_nas') as pull:
            result = safe_sync_once(self.db, 'http://nas', 'token', 'test')
        self.assertEqual(result['action'], 'conflict')
        self.assertFalse(result['ok'])
        push.assert_not_called(); pull.assert_not_called()

    def test_signature_changes_when_revision_is_added(self):
        before = database_logical_signature(self.base)
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)", ('R-003','LPS','Další'))
        after = database_logical_signature(self.base)
        self.assertNotEqual(before, after)

    def remote_bundle(self, remote):
        bundle = self.tmp / 'remote.zip'
        snapshot = self.tmp / 'remote_snapshot.db'
        with sqlite3.connect(remote) as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        manifest = {'format': 'PZ-REVIZE-SNAPSHOT-1', 'generation': 8,
                    'db_sha256': _sha256(snapshot), 'missing_file_count': 0}
        with zipfile.ZipFile(bundle, 'w') as z:
            z.write(snapshot, 'pz_revize.db')
            z.writestr('manifest.json', json.dumps(manifest))
        return bundle

    def test_manual_pull_cannot_erase_unsent_revision(self):
        remote = self.copy('server.db')
        bundle = self.remote_bundle(remote)
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                        ('R-LOCAL', 'ELEKTRO', 'Nevyexportovaná revize'))
        data_dir = self.tmp / 'appdata'; (data_dir / 'backups').mkdir(parents=True)
        with patch('pzrevize.nas_sync.app_data_dir', return_value=data_dir), \
             patch('pzrevize.nas_sync._download_bundle', side_effect=lambda u,t,d: (shutil.copy2(bundle,d),8)[1]):
            with self.assertRaises(NasConflictError):
                pull_from_nas(self.db, 'http://nas', 'token')
        self.assertEqual(self.db.fetchone("SELECT subject FROM revisions WHERE revision_no='R-LOCAL'")[0],
                         'Nevyexportovaná revize')
        self.assertTrue(list((data_dir / 'backups').glob('*.zip')))

    def test_local_edit_during_download_blocks_pull(self):
        remote = self.copy('server.db')
        bundle = self.remote_bundle(remote)
        data_dir = self.tmp / 'appdata'; (data_dir / 'backups').mkdir(parents=True)
        def download(url, token, dest):
            shutil.copy2(bundle, dest)
            self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                            ('R-DURING', 'ELEKTRO', 'Uloženo během stahování'))
            return 8
        with patch('pzrevize.nas_sync.app_data_dir', return_value=data_dir), \
             patch('pzrevize.nas_sync._download_bundle', side_effect=download):
            with self.assertRaises(NasConflictError):
                pull_from_nas(self.db, 'http://nas', 'token')
        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no='R-DURING'"))

    def test_editor_opened_during_pull_blocks_replacement(self):
        remote = self.copy('server.db')
        bundle = self.remote_bundle(remote)
        data_dir = self.tmp / 'appdata'; (data_dir / 'backups').mkdir(parents=True)
        editor_open = False
        def download(url, token, dest):
            nonlocal editor_open
            shutil.copy2(bundle, dest); editor_open = True
            return 8
        with patch('pzrevize.nas_sync.app_data_dir', return_value=data_dir), \
             patch('pzrevize.nas_sync._download_bundle', side_effect=download):
            with self.assertRaises(NasSyncError):
                pull_from_nas(self.db, 'http://nas', 'token', can_pull=lambda: not editor_open)

    def test_push_does_not_mark_a_later_edit_as_synchronized(self):
        before = database_logical_signature(self.base)
        def remote_accept(*args):
            self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                            ('R-DURING-PUSH', 'ELEKTRO', 'Uloženo během odesílání'))
            return {'generation': 3}
        with patch('pzrevize.nas_sync._post_bundle', side_effect=remote_accept):
            push_to_nas(self.db, 'http://nas', 'token', 'test', expected_generation=2)
        self.assertNotEqual(before, database_logical_signature(self.base))
        self.assertEqual(self.db.fetchone("SELECT value FROM settings WHERE key='nas_last_signature'")[0], before)

    def test_local_standard_catalog_document_blocks_replacement(self):
        remote = self.copy('server.db')
        self.db.execute("INSERT INTO standard_catalog_documents(catalog_key,designation,catalog_version) VALUES(?,?,?)",
                        ('local-only', 'ČSN test', 'local'))
        self.assertEqual(compare_database_states(self.base, remote)['relation'], 'local_superset')

    def test_two_pcs_with_independent_revisions_stop_as_conflict(self):
        remote = self.copy('server.db')
        with sqlite3.connect(remote) as con:
            con.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                        ('R-PC2', 'ELEKTRO', 'Z druhého PC'))
        self.db.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                        ('R-PC1', 'ELEKTRO', 'Z prvního PC'))
        comparison = compare_database_states(self.base, remote)
        self.assertEqual(comparison['relation'], 'conflict')
        self.assertEqual(comparison['local_only_revisions'], ['R-PC1'])
        self.assertEqual(comparison['remote_only_revisions'], ['R-PC2'])
        set_setting(self.db, 'nas_generation', '4')
        with patch('pzrevize.nas_sync.get_status', return_value={'generation': 7}), \
             patch('pzrevize.nas_sync.compare_with_nas', return_value={**comparison, 'generation': 7}), \
             patch('pzrevize.nas_sync.push_to_nas') as push, \
             patch('pzrevize.nas_sync.pull_from_nas') as pull:
            result = safe_sync_once(self.db, 'http://nas', 'token', 'test')
        self.assertEqual(result['action'], 'conflict')
        push.assert_not_called(); pull.assert_not_called()
        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no='R-PC1'"))

    def test_remote_superset_can_be_pulled(self):
        remote = self.copy('server.db')
        with sqlite3.connect(remote) as con:
            con.execute("INSERT INTO revisions(revision_no,revision_type,subject) VALUES(?,?,?)",
                        ('R-REMOTE', 'ELEKTRO', 'Ze serveru'))
        bundle = self.remote_bundle(remote)
        data_dir = self.tmp / 'appdata'; (data_dir / 'backups').mkdir(parents=True)
        with patch('pzrevize.nas_sync.app_data_dir', return_value=data_dir), \
             patch('pzrevize.nas_sync._download_bundle', side_effect=lambda u,t,d: (shutil.copy2(bundle,d),8)[1]):
            result = pull_from_nas(self.db, 'http://nas', 'token')
        self.assertEqual(result['counts']['revisions'], 2)
        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no='R-001'"))
        self.assertIsNotNone(self.db.fetchone("SELECT id FROM revisions WHERE revision_no='R-REMOTE'"))


if __name__ == '__main__':
    unittest.main()
