import json
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import gmailkeeper as keeper


class FakeGmail:
    created_labels = created_filters = 0

    def __init__(self, messages, fail=False):
        self.messages = messages
        self.fail = fail
        self.changes = []
        self.rules = []

    def call(self, path, **kwargs):
        return {'historyId': '100'}

    def list_ids(self, query):
        return [message['id'] for message in self.messages]

    def metadata(self, ids):
        return [message for message in self.messages if message['id'] in ids]

    def label(self, name):
        return name

    def filter(self, label, query):
        self.rules.append((label, query))

    def modify(self, ids, add, remove):
        if self.fail:
            raise RuntimeError('Simulated Gmail failure')
        self.changes.append((ids, add, remove))


def message(identifier, sender, labels):
    return {'id': identifier, 'labelIds': labels, 'payload': {'headers': [{'name': 'From', 'value': sender}]}}


class MaintenanceTests(unittest.TestCase):
    def test_brand_uses_domain_even_when_visible_name_is_personal(self):
        self.assertEqual(keeper.identify('A person', 'notifications@github.com', {'github.com': 'GitHub'}), ('github.com', 'GitHub'))

    def test_lookalike_domain_is_not_known_brand(self):
        self.assertEqual(keeper.identify('GitHub', 'notify@notgithub.com', {'github.com': 'GitHub'}), (None, None))

    def test_personal_address_stays_pending(self):
        self.assertEqual(keeper.identify('Amazon', 'amazon@gmail.com', {}), (None, None))

    def test_malformed_domain_cannot_become_a_filter_query(self):
        self.assertEqual(keeper.identify('Example', 'news@example.com OR from:other.com', {}), (None, None))

    def test_new_brand_requires_agreement_between_name_and_domain(self):
        self.assertEqual(keeper.identify('Amazon', 'news@mail.amazon.es', {}), ('amazon.es', 'Amazon'))
        self.assertEqual(keeper.identify('Amazon', 'news@unrelated.es', {}), (None, None))

    def test_new_brand_drops_sender_description(self):
        self.assertEqual(keeper.identify('Recibos de Uber', 'news@uber.com', {}), ('uber.com', 'Uber'))

    def test_multiword_brand_matches_normalized_domain(self):
        self.assertEqual(keeper.identify('El Corte Inglés', 'news@elcorteingles.es', {}), ('elcorteingles.es', 'El Corte Inglés'))

    def test_explicit_sender_overrides_shared_domain(self):
        self.assertEqual(keeper.identify('Someone', 'ana@gmail.com', {'ana@gmail.com': 'Ana'}), ('ana@gmail.com', 'Ana'))

    def run_sync(self, gmail, directory):
        with patch.object(keeper, 'STATE_DIR', Path(directory)), redirect_stdout(io.StringIO()):
            keeper.sync(gmail, 150)

    def test_classifies_archives_and_preserves_read_and_existing_labels(self):
        gmail = FakeGmail([message('1', 'LinkedIn <notifications-noreply@linkedin.com>', ['INBOX', 'UNREAD', 'CATEGORY_SOCIAL', 'Empleo'])])
        with tempfile.TemporaryDirectory() as directory:
            self.run_sync(gmail, directory)
            state = json.loads((Path(directory) / 'state.json').read_text(encoding='utf-8'))
        self.assertEqual(state['queue'], [])
        self.assertEqual(gmail.changes, [(['1'], ['Archivo/Social', 'Archivo/Social/LinkedIn'], ['INBOX', 'Archivo/Pendiente de marca'])])

    def test_unknown_sender_is_archived_and_marked_pending(self):
        gmail = FakeGmail([message('1', 'Someone <someone@gmail.com>', ['INBOX', 'CATEGORY_PERSONAL'])])
        with tempfile.TemporaryDirectory() as directory:
            self.run_sync(gmail, directory)
        self.assertEqual(gmail.rules, [])
        self.assertEqual(gmail.changes, [(['1'], ['Archivo/Personal', 'Archivo/Pendiente de marca'], ['INBOX'])])

    def test_sent_drafts_chat_spam_trash_are_excluded(self):
        gmail = FakeGmail([message(str(i), 'GitHub <notify@github.com>', [label]) for i, label in enumerate(['SENT', 'DRAFT', 'CHAT', 'SPAM', 'TRASH'])])
        with tempfile.TemporaryDirectory() as directory:
            self.run_sync(gmail, directory)
        self.assertEqual(gmail.changes, [])

    def test_no_duplicate_modification_when_already_classified(self):
        gmail = FakeGmail([message('1', 'GitHub <notify@github.com>', ['CATEGORY_UPDATES', 'Archivo/Actualizaciones', 'Archivo/Actualizaciones/GitHub', 'UNREAD'])])
        with tempfile.TemporaryDirectory() as directory:
            self.run_sync(gmail, directory)
        self.assertEqual(gmail.changes, [])

    def test_failed_write_does_not_remove_message_from_queue(self):
        gmail = FakeGmail([message('1', 'GitHub <notify@github.com>', ['INBOX'])], fail=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                self.run_sync(gmail, directory)
            state = json.loads((Path(directory) / 'state.json').read_text(encoding='utf-8'))
        self.assertEqual(state['queue'], ['1'])
        self.assertEqual(state['processed'], 0)

    def test_history_prioritizes_new_message_without_losing_backfill(self):
        gmail = FakeGmail([message('old', 'Old <old@gmail.com>', []), message('new', 'GitHub <notify@github.com>', ['INBOX'])])
        gmail.call = Mock(return_value={'historyId': '101', 'history': [{'messagesAdded': [{'message': {'id': 'new'}}]}]})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            keeper.save(path, {'history_id': '100', 'queue': ['old'], 'brands': {}, 'processed': 0})
            with patch.object(keeper, 'STATE_DIR', Path(directory)), redirect_stdout(io.StringIO()):
                keeper.sync(gmail, 1)
            state = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(state['queue'], ['old'])
        self.assertEqual(state['history_id'], '101')
        self.assertEqual(gmail.changes[0][0], ['new'])

    def test_existing_native_filter_is_reused(self):
        gmail = keeper.Gmail.__new__(keeper.Gmail)
        gmail.filters = [{'criteria': {'query': keeper.ELIGIBLE + ' category:social'}, 'action': {'addLabelIds': ['social'], 'removeLabelIds': ['INBOX']}}]
        gmail.call = Mock()
        gmail.filter('social', 'category:social')
        gmail.call.assert_not_called()

    def test_history_message_outside_configured_scope_is_untouched(self):
        gmail = FakeGmail([message('excluded', 'GitHub <notify@github.com>', ['INBOX', 'UNREAD'])])
        gmail.call = Mock(return_value={'historyId': '101', 'history': [{'messagesAdded': [{'message': {'id': 'excluded'}}]}]})
        gmail.list_ids = Mock(return_value=[])
        with tempfile.TemporaryDirectory() as directory:
            keeper.save(Path(directory) / 'state.json', {'history_id': '100', 'queue': [], 'brands': {}, 'processed': 0})
            with patch.object(keeper, 'RESTRICTED', True):
                self.run_sync(gmail, directory)
        self.assertEqual(gmail.changes, [])

    def test_preview_makes_no_gmail_mutations(self):
        gmail = FakeGmail([message('1', 'GitHub <notify@github.com>', ['INBOX', 'UNREAD'])])
        gmail.call = Mock(return_value={'messages': [{'id': '1'}]})
        gmail.filters = []
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            keeper.preview(gmail, 20, Path(directory) / 'sample.json')
        self.assertEqual(gmail.changes, [])
        self.assertEqual(gmail.rules, [])
        gmail.call.assert_called_once()

    def test_remove_filters_preserves_user_filters(self):
        gmail = keeper.Gmail.__new__(keeper.Gmail)
        gmail.filters = [{'id': 'mine'}, {'id': 'user'}]
        gmail.call = Mock(return_value={})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'owned-filters.json'
            keeper.save(path, ['mine'])
            with patch.object(keeper, 'STATE_DIR', Path(directory)), redirect_stdout(io.StringIO()):
                keeper.remove_filters(gmail)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), [])
        gmail.call.assert_called_once_with('settings/filters/mine', 'DELETE')

    def test_manual_canonical_brand_overrides_learned_name(self):
        gmail = FakeGmail([message('1', 'Warp Team <news@warp.dev>', ['INBOX', 'CATEGORY_UPDATES'])])
        gmail.call = Mock(return_value={'historyId': '101'})
        with tempfile.TemporaryDirectory() as directory:
            keeper.save(Path(directory) / 'state.json', {'history_id': '100', 'queue': ['1'], 'brands': {'warp.dev': 'Warp Team'}, 'processed': 0})
            with patch.object(keeper, 'BRAND_OVERRIDES', {'warp.dev': 'Warp'}):
                self.run_sync(gmail, directory)
        self.assertIn('Archivo/Actualizaciones/Warp', gmail.changes[0][1])

    def test_filter_creation_can_be_disabled(self):
        gmail = keeper.Gmail.__new__(keeper.Gmail)
        gmail.call = Mock()
        with patch.object(keeper, 'CREATE_FILTERS', False):
            gmail.filter('label', 'category:social')
        gmail.call.assert_not_called()


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        keys = ['ACCOUNT', 'CREDENTIALS', 'STATE_DIR', 'BRANDS_FILE', 'BRAND_OVERRIDES', 'PREFIX', 'ELIGIBLE', 'RESTRICTED', 'LEARN_BRANDS', 'CREATE_FILTERS']
        self.original = {key: getattr(keeper, key) for key in keys}
        self.addCleanup(lambda: [setattr(keeper, key, value) for key, value in self.original.items()])
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / 'config.json'
        self.config = {'account': 'persona@gmail.com', 'credentials': str(self.root / 'token.json'), 'state_dir': str(self.root / 'state'), 'brands_file': None, 'brands': {}, 'label_prefix': 'Archivo'}
        keeper.save(self.path, self.config)

    def test_account_and_credentials_are_configurable(self):
        keeper.configure(self.path)
        self.assertEqual(keeper.ACCOUNT, 'persona@gmail.com')
        self.assertEqual(keeper.CREDENTIALS, self.root / 'token.json')

    def test_init_creates_separate_private_profile_paths(self):
        target = self.root / 'new-profile.json'
        with patch.object(Path, 'home', return_value=self.root), redirect_stdout(io.StringIO()):
            keeper.initialize(target, 'persona@example.org')
        config = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(config['account'], 'persona@example.org')
        self.assertTrue(Path(config['credentials']).is_relative_to(self.root))
        self.assertTrue(Path(config['state_dir']).is_relative_to(self.root))

    def test_configuration_preserves_utf8_names(self):
        self.config['brands'] = {'family@example.org': 'Mamá'}
        keeper.save(self.path, self.config)
        self.assertIn('Mamá'.encode('utf-8'), self.path.read_bytes())
        keeper.configure(self.path)
        self.assertEqual(keeper.load_brands()['family@example.org'], 'Mamá')

    def test_cannot_reuse_state_for_another_account(self):
        keeper.configure(self.path)
        self.config['account'] = 'otra@gmail.com'
        keeper.save(self.path, self.config)
        with self.assertRaises(ValueError):
            keeper.configure(self.path)

    def test_cannot_reuse_state_for_changed_policy(self):
        keeper.configure(self.path)
        self.config['query'] = 'category:promotions'
        keeper.save(self.path, self.config)
        with self.assertRaises(ValueError):
            keeper.configure(self.path)

    def test_exclusions_are_part_of_native_filter_query(self):
        self.config['exclude_senders'] = ['family@example.org']
        keeper.save(self.path, self.config)
        keeper.configure(self.path)
        self.assertIn('-from:family@example.org', keeper.ELIGIBLE)
        self.assertTrue(keeper.RESTRICTED)

    def test_requires_apply_before_connecting_for_mutations(self):
        with patch.object(sys, 'argv', ['gmailkeeper.py', 'sync', '--config', str(self.path)]), patch.object(keeper, 'Gmail') as gmail, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                keeper.main()
        self.assertEqual(error.exception.code, 2)
        gmail.assert_not_called()

    def test_auth_wrong_account_does_not_save_credentials(self):
        keeper.configure(self.path)
        credentials = SimpleNamespace(token='fake-test-token', refresh_token='fake-test-refresh', to_json=lambda: '{}')
        module = ModuleType('google_auth_oauthlib.flow')
        module.InstalledAppFlow = Mock()
        module.InstalledAppFlow.from_client_secrets_file.return_value.run_local_server.return_value = credentials
        response = io.BytesIO(json.dumps({'emailAddress': 'otra@gmail.com'}).encode())
        with patch.dict(sys.modules, {'google_auth_oauthlib': ModuleType('google_auth_oauthlib'), 'google_auth_oauthlib.flow': module}), patch.object(keeper.urllib.request, 'urlopen', return_value=response):
            with self.assertRaises(ValueError):
                keeper.authorize(self.root / 'client.json')
        self.assertFalse(keeper.CREDENTIALS.exists())

    def test_preview_snapshot_cannot_be_verified_in_another_account(self):
        keeper.configure(self.path)
        snapshot = self.root / 'sample.json'
        keeper.save(snapshot, {'account': 'otra@gmail.com', 'sample': []})
        with self.assertRaises(ValueError):
            keeper.verify(Mock(), snapshot)


if __name__ == '__main__':
    unittest.main()
