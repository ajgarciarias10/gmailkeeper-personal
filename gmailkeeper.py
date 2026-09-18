#!/usr/bin/env python3
"""Organiza tu Gmail por remitente y archiva sin borrar ni marcar como leído."""
import argparse
from collections import defaultdict
import email
import email.policy
import email.utils
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ACCOUNT = None
DEFAULT_CONFIG = Path.home() / '.config/gmailkeeper/config.json'
CREDENTIALS = Path.home() / '.config/gmailkeeper/token.json'
STATE_DIR = Path.home() / '.local/state/gmailkeeper'
BRANDS_FILE = Path(__file__).with_name('brands.json')
BRAND_OVERRIDES = {}
PREFIX = 'Archivo'
BASE_ELIGIBLE = '-in:sent -in:drafts -in:chats -in:spam -in:trash'
ELIGIBLE = BASE_ELIGIBLE
RESTRICTED = False
LEARN_BRANDS = True
CREATE_FILTERS = True
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.settings.basic']
CATEGORIES = [
    ('CATEGORY_PROMOTIONS', 'Promociones', 'category:promotions'),
    ('CATEGORY_UPDATES', 'Actualizaciones', 'category:updates'),
    ('CATEGORY_SOCIAL', 'Social', 'category:social'),
    ('CATEGORY_FORUMS', 'Foros', 'category:forums'),
    ('CATEGORY_PERSONAL', 'Personal', 'category:personal'),
    (None, 'Otros', '-category:promotions -category:updates -category:social -category:forums -category:personal'),
]


def save(path, data):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temporary.replace(path)


def valid_rule_key(value):
    domain = value.partition('@')[2] if '@' in value else value
    return bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+', domain)) and not any(char.isspace() for char in value)


def load_brands():
    brands = json.loads(BRANDS_FILE.read_text(encoding='utf-8')) if BRANDS_FILE else {}
    if not isinstance(brands, dict):
        raise ValueError('brands_file debe contener un objeto JSON')
    brands = brands | BRAND_OVERRIDES
    for key, name in brands.items():
        if not isinstance(key, str) or not valid_rule_key(key.lower()) or not isinstance(name, str) or not name.strip() or '/' in name or any(ord(char) < 32 for char in name) or len(name) > 100:
            raise ValueError('Regla de marca inválida: ' + str(key))
    return {key.lower(): name.strip() for key, name in brands.items()}


def configure(path):
    global ACCOUNT, CREDENTIALS, STATE_DIR, BRANDS_FILE, BRAND_OVERRIDES, PREFIX
    global ELIGIBLE, RESTRICTED, LEARN_BRANDS, CREATE_FILTERS
    config = json.loads(path.read_text(encoding='utf-8'))
    ACCOUNT = config.get('account', '').strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', ACCOUNT):
        raise ValueError('Configura account con tu dirección de Gmail')
    def resolve(value):
        candidate = Path(value).expanduser()
        return candidate if candidate.is_absolute() else (path.parent / candidate).resolve()
    CREDENTIALS = resolve(config['credentials'])
    STATE_DIR = resolve(config['state_dir'])
    BRANDS_FILE = resolve(config['brands_file']) if config.get('brands_file') else None
    BRAND_OVERRIDES = config.get('brands', {})
    if not isinstance(BRAND_OVERRIDES, dict):
        raise ValueError('brands debe ser un objeto JSON')
    PREFIX = config.get('label_prefix', 'Archivo').strip()
    if not PREFIX or any(not component.strip() for component in PREFIX.split('/')) or any(ord(char) < 32 for char in PREFIX) or len(PREFIX) > 100:
        raise ValueError('label_prefix inválido')
    extra = config.get('query', '').strip()
    exclusions = config.get('exclude_senders', [])
    if not isinstance(exclusions, list) or any(not isinstance(sender, str) or not valid_rule_key(sender.lower()) for sender in exclusions):
        raise ValueError('exclude_senders debe contener direcciones o dominios válidos')
    ELIGIBLE = BASE_ELIGIBLE + (' (' + extra + ')' if extra else '') + ''.join(' -from:' + sender.lower() for sender in exclusions)
    RESTRICTED = bool(extra or exclusions)
    LEARN_BRANDS = config.get('learn_brands', True)
    CREATE_FILTERS = config.get('create_filters', True)
    if not isinstance(LEARN_BRANDS, bool) or not isinstance(CREATE_FILTERS, bool):
        raise ValueError('learn_brands y create_filters deben ser true o false')
    load_brands()
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = {'account': ACCOUNT, 'label_prefix': PREFIX, 'query': ELIGIBLE}
    binding = STATE_DIR / 'profile.json'
    if binding.exists() and json.loads(binding.read_text(encoding='utf-8')) != identity:
        raise ValueError('Este state_dir pertenece a otra cuenta o reglas. Usa un state_dir nuevo; revisa primero los filtros antiguos en Gmail.')
    if not binding.exists():
        save(binding, identity)


def initialize(path, account, existing_credentials=None):
    if not account or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', account):
        raise ValueError('Usa init --account tu-correo@gmail.com')
    if path.exists():
        raise ValueError('La configuración ya existe; edítala para personalizarla')
    profile = hashlib.sha256(account.lower().encode()).hexdigest()[:12]
    private = Path.home() / '.config/gmailkeeper/profiles' / profile
    state = Path.home() / '.local/state/gmailkeeper/profiles' / profile
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    save(path, {'account': account.lower(), 'credentials': str(Path(existing_credentials).expanduser().resolve()) if existing_credentials else str(private / 'token.json'), 'state_dir': str(state), 'brands_file': str(Path(__file__).with_name('brands.json').resolve()), 'label_prefix': 'Archivo', 'query': '', 'exclude_senders': [], 'brands': {}, 'learn_brands': True, 'create_filters': True})
    print('Configuración creada:', path)


@contextmanager
def maintenance_lock():
    with (STATE_DIR / 'lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                print('Otra revisión está en curso; se retomará en la siguiente ejecución.')
                yield False
                return
            try:
                yield True
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Otra revisión está en curso; se retomará en la siguiente ejecución.')
                yield False
                return
            yield True


def authorize(client_secret):
    if not client_secret:
        raise ValueError('Usa auth --client-secret /ruta/client_secret.json')
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ValueError('Instala las dependencias: python -m pip install -r requirements.txt') from None
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    credentials = flow.run_local_server(port=0, login_hint=ACCOUNT, prompt='consent', access_type='offline')
    if not credentials.refresh_token:
        raise ValueError('Google no ha entregado un refresh token. Vuelve a autorizar.')
    request = urllib.request.Request('https://gmail.googleapis.com/gmail/v1/users/me/profile', headers={'Authorization': 'Bearer ' + credentials.token})
    profile = json.load(urllib.request.urlopen(request, timeout=30))
    if profile['emailAddress'].lower() != ACCOUNT:
        raise ValueError('Has autorizado otra cuenta. Las credenciales no se han guardado.')
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    save(CREDENTIALS, json.loads(credentials.to_json()))
    print('Cuenta autorizada:', ACCOUNT)


class Gmail:
    def __init__(self):
        self.ready = time.monotonic()
        self.refresh()
        if not ACCOUNT or self.call('profile')['emailAddress'].lower() != ACCOUNT:
            raise RuntimeError('Unexpected Gmail account; stopped')
        self.labels = {label['name']: label['id'] for label in self.call('labels')['labels']}
        self.filters = self.call('settings/filters').get('filter', [])
        self.created_labels = self.created_filters = 0

    def refresh(self):
        credentials = json.loads(CREDENTIALS.read_text(encoding='utf-8'))
        payload = urllib.parse.urlencode({key: credentials[key] for key in ('client_id', 'client_secret', 'refresh_token')} | {'grant_type': 'refresh_token'}).encode()
        request = urllib.request.Request('https://oauth2.googleapis.com/token', data=payload)
        result = json.load(urllib.request.urlopen(request, timeout=30))
        granted = result.get('scope', '').split() or credentials.get('scopes', [])
        required = SCOPES if CREATE_FILTERS else SCOPES[:1]
        if not set(required).issubset(granted):
            raise RuntimeError('Faltan permisos de Gmail; vuelve a ejecutar auth')
        self.token = result['access_token']
        self.expires = time.monotonic() + result.get('expires_in', 3600) - 120

    def request(self, url, method='GET', data=None, content_type='application/json', units=5):
        if time.monotonic() >= self.expires:
            self.refresh()
        for attempt in range(7):
            time.sleep(max(0, self.ready - time.monotonic()))
            # Stay under the current 6,000 units/minute user quota.
            self.ready = time.monotonic() + units / 65
            request = urllib.request.Request(url, data=data, method=method, headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': content_type})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read(), response.headers
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 6:
                    raise RuntimeError(f'Gmail HTTP {error.code} at {url.split("?")[0]}') from None
                time.sleep(min(2 ** (attempt + 1) + random.random(), 45))
        raise RuntimeError('Retry limit reached')

    def call(self, path, method='GET', payload=None, params=None, units=5):
        url = 'https://gmail.googleapis.com/gmail/v1/users/me/' + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        body = json.dumps(payload).encode() if payload is not None else None
        raw, _ = self.request(url, method, body, units=units)
        return json.loads(raw) if raw else {}

    def list_ids(self, query):
        result, page = [], None
        while True:
            params = {'q': query, 'maxResults': 500}
            if page:
                params['pageToken'] = page
            response = self.call('messages', params=params)
            result.extend(item['id'] for item in response.get('messages', []))
            page = response.get('nextPageToken')
            if not page:
                return result

    def label(self, name):
        if name not in self.labels:
            self.labels[name] = self.call('labels', 'POST', {'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'})['id']
            self.created_labels += 1
        return self.labels[name]

    def filter(self, label_id, query):
        if not CREATE_FILTERS:
            return
        criteria = {'query': ELIGIBLE + ' ' + query}
        action = {'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}
        if any(item.get('criteria') == criteria and item.get('action') == action for item in self.filters):
            return
        if len(self.filters) >= 990:
            # Keep classification and archiving working through the timer.
            return
        result = self.call('settings/filters', 'POST', {'criteria': criteria, 'action': action})
        self.filters.append(result)
        self.created_filters += 1
        path = STATE_DIR / 'owned-filters.json'
        owned = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        save(path, list(dict.fromkeys(owned + [result['id']])))

    def modify(self, ids, add, remove):
        for start in range(0, len(ids), 1000):
            self.call('messages/batchModify', 'POST', {'ids': ids[start:start + 1000], 'addLabelIds': add, 'removeLabelIds': remove}, units=50)

    def metadata(self, ids):
        result = []
        for start in range(0, len(ids), 20):
            boundary, parts = 'gmailkeeper_batch', []
            for message_id in ids[start:start + 20]:
                path = '/gmail/v1/users/me/messages/' + message_id + '?format=metadata&metadataHeaders=From&fields=id,labelIds,payload/headers'
                parts.append(f'--{boundary}\r\nContent-Type: application/http\r\nContent-ID: <{message_id}>\r\n\r\nGET {path} HTTP/1.1\r\n\r\n')
            body = (''.join(parts) + f'--{boundary}--\r\n').encode()
            raw, headers = self.request('https://gmail.googleapis.com/batch/gmail/v1', 'POST', body, 'multipart/mixed; boundary=' + boundary, units=len(parts) * 20)
            mime = email.message_from_bytes(('Content-Type: ' + headers['Content-Type'] + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw, policy=email.policy.default)
            seen = set()
            for part in mime.iter_parts():
                message_id = part['Content-ID'].strip('<>').removeprefix('response-')
                seen.add(message_id)
                response = part.get_payload(decode=True).decode()
                status = int(response.splitlines()[0].split()[1])
                if status == 404:
                    continue
                if status in (429, 500, 502, 503, 504):
                    message = self.call('messages/' + message_id, params={'format': 'metadata', 'metadataHeaders': 'From', 'fields': 'id,labelIds,payload/headers'}, units=20)
                elif status == 200:
                    message = json.loads(response.split('\r\n\r\n', 1)[1])
                else:
                    raise RuntimeError(f'Metadata HTTP {status}')
                result.append(message)
            if seen != set(ids[start:start + 20]):
                raise RuntimeError('Incomplete metadata batch; state not advanced')
        return result


def domain_query(domain):
    return 'from:' + domain


def bootstrap(gmail):
    brands = load_brands()
    matched = set()
    for _, category, query in CATEGORIES:
        parent = gmail.label(PREFIX + '/' + category)
        gmail.filter(parent, query)
        inbox = gmail.list_ids('in:inbox ' + ELIGIBLE + ' ' + query)
        gmail.modify(inbox, [parent], ['INBOX'])
        print(f'{PREFIX}/{category}: archivados {len(inbox)}', flush=True)
    for domain, brand in brands.items():
        brand_count = 0
        for _, category, query in CATEGORIES:
            search = domain_query(domain) + ' ' + query
            ids = gmail.list_ids(ELIGIBLE + ' ' + search)
            if not ids:
                continue
            parent = gmail.label(PREFIX + '/' + category)
            child = gmail.label(PREFIX + '/' + category + '/' + brand)
            gmail.filter(child, search)
            gmail.modify(ids, [parent, child], ['INBOX'])
            matched.update(ids)
            brand_count += len(ids)
        print(f'{brand}: etiquetados {brand_count}', flush=True)
    print(json.dumps({'historical_messages_classified': len(matched), 'labels_created': gmail.created_labels, 'filters_created': gmail.created_filters}), flush=True)
    save(STATE_DIR / 'bootstrap.json', {'known_domains': list(brands), 'historical_messages_classified': len(matched)})


def normalize(value):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())


def identify(name, address, brands):
    if address in brands:
        return address, brands[address]
    domain = address.partition('@')[2]
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+', domain):
        return None, None
    for root, brand in sorted(brands.items(), key=lambda item: len(item[0]), reverse=True):
        if domain == root or domain.endswith('.' + root):
            return root, brand
    if not LEARN_BRANDS:
        return None, None
    # A new name is accepted only when it agrees with a corporate domain.
    # Personal mail providers stay pending; visible names alone are insufficient.
    personal = {'gmail.com', 'googlemail.com', 'hotmail.com', 'hotmail.es', 'outlook.com', 'outlook.es', 'yahoo.com', 'yahoo.es', 'live.com', 'icloud.com', 'proton.me', 'protonmail.com', 'aol.com', 'mail.com', 'gmx.com', 'gmx.es'}
    parts = domain.split('.')
    if len(parts) < 2 or any(domain == p or domain.endswith('.' + p) for p in personal):
        return None, None
    compound = {'co.uk', 'com.au', 'com.br', 'co.jp', 'co.nz', 'com.mx', 'com.ar', 'org.uk', 'com.pt', 'com.es'}
    root = '.'.join(parts[-3:] if '.'.join(parts[-2:]) in compound else parts[-2:])
    stem = root.split('.')[0]
    clean = re.sub(r'[/®™\x00-\x1f]', ' ', name).strip()
    words = re.split(r'\W+', clean)
    brand = clean if normalize(clean) == normalize(stem) else next((word for word in words if normalize(word) == normalize(stem)), '')
    if len(stem) < 4:
        return None, None
    if not brand or len(brand) > 60:
        return None, None
    return root, brand


def sync(gmail, limit):
    path = STATE_DIR / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'brands': {}, 'queue': [], 'history_id': None, 'processed': 0}
    seed = load_brands()
    state['brands'] = state['brands'] | seed
    matching = set(gmail.list_ids(ELIGIBLE)) if RESTRICTED else None
    if state['history_id'] is None:
        # Capture history before taking the snapshot to avoid missing new arrivals.
        state['history_id'] = gmail.call('profile')['historyId']
        bootstrap_path = STATE_DIR / 'bootstrap.json'
        already_classified = json.loads(bootstrap_path.read_text(encoding='utf-8')).get('known_domains', []) if bootstrap_path.exists() else []
        search = ELIGIBLE + ''.join(' -from:' + domain for domain in already_classified)
        # Also cover messages that arrived during bootstrap, before this cursor.
        recent = gmail.list_ids(ELIGIBLE + ' newer_than:7d')
        state['queue'] = list(dict.fromkeys(recent + gmail.list_ids(search)))
        save(path, state)
    else:
        page, new_ids = None, []
        while True:
            params = {'startHistoryId': state['history_id'], 'historyTypes': 'messageAdded', 'maxResults': 500}
            if page:
                params['pageToken'] = page
            try:
                history = gmail.call('history', params=params, units=2)
            except RuntimeError as error:
                if 'HTTP 404' not in str(error):
                    raise
                # Gmail expires history. Recover with a fresh complete scan.
                state['history_id'] = gmail.call('profile')['historyId']
                state['queue'] = list(dict.fromkeys(gmail.list_ids(ELIGIBLE) + state['queue']))
                save(path, state)
                break
            for item in history.get('history', []):
                new_ids.extend(change['message']['id'] for change in item.get('messagesAdded', []))
            page = history.get('nextPageToken')
            if not page:
                state['queue'] = list(dict.fromkeys(new_ids + state['queue']))
                state['history_id'] = history['historyId']
                save(path, state)
                break
    selected = state['queue'][:limit]
    pending = gmail.label(PREFIX + '/Pendiente de marca')
    groups = defaultdict(list)
    unknown = 0
    for message in gmail.metadata(selected):
        if matching is not None and message['id'] not in matching:
            continue
        labels = message.get('labelIds', [])
        if any(label in labels for label in ('SENT', 'DRAFT', 'CHAT', 'TRASH', 'SPAM')):
            continue
        sender = next((header['value'] for header in message.get('payload', {}).get('headers', []) if header['name'].lower() == 'from'), '')
        name, address = email.utils.parseaddr(sender)
        domain, brand = identify(name, address.lower(), state['brands'])
        _, category, query = next((item for item in CATEGORIES if item[0] in labels), CATEGORIES[-1])
        parent = gmail.label(PREFIX + '/' + category)
        if brand:
            state['brands'][domain] = brand
            child = gmail.label(PREFIX + '/' + category + '/' + brand)
            gmail.filter(child, domain_query(domain) + ' ' + query)
            add, remove = [parent, child], ['INBOX', pending]
        else:
            add, remove = [parent, pending], ['INBOX']
            unknown += 1
        if set(add).issubset(labels) and not set(remove).intersection(labels):
            continue
        groups[(tuple(add), tuple(remove))].append(message['id'])
    for (add, remove), ids in groups.items():
        gmail.modify(ids, list(add), list(remove))
    state['queue'] = state['queue'][len(selected):]
    state['processed'] += len(selected)
    save(path, state)
    print(json.dumps({'processed_now': len(selected), 'processed_total': state['processed'], 'backfill_remaining': len(state['queue']), 'pending_brand_now': unknown, 'known_domains': len(state['brands']), 'labels_created': gmail.created_labels, 'filters_created': gmail.created_filters}), flush=True)


def verify(gmail, snapshot_path):
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    if snapshot.get('account') != ACCOUNT:
        raise ValueError('La muestra pertenece a otra cuenta')
    before = {row['id']: row for row in snapshot['sample']}
    messages = gmail.metadata(list(before))
    if len(messages) != len(before):
        raise RuntimeError('Verification sample incomplete')
    classified = 0
    brand_ids = {label_id for name, label_id in gmail.labels.items() if name.startswith(PREFIX + '/') and name.count('/') >= PREFIX.count('/') + 2}
    for message in messages:
        previous = set(before[message['id']]['labels'])
        current = set(message.get('labelIds', []))
        allowed_removed = {'INBOX', gmail.labels.get(PREFIX + '/Pendiente de marca')}
        if not (previous - allowed_removed).issubset(current):
            raise RuntimeError('A preexisting label is missing')
        if ('UNREAD' in previous) != ('UNREAD' in current):
            raise RuntimeError('Read state differs from the original snapshot')
        if 'INBOX' in current:
            raise RuntimeError('Sample message remains in the inbox')
        classified += bool(current & brand_ids)
    original_filters = {item['id'] for item in snapshot['filters']}
    if not original_filters.issubset({item['id'] for item in gmail.filters}):
        raise RuntimeError('A preexisting filter is missing')
    print(json.dumps({'verified_messages': len(messages), 'brand_classified_in_sample': classified, 'existing_labels_preserved': True, 'read_state_preserved': True, 'existing_filters_preserved': True}), flush=True)


def status(gmail):
    path = STATE_DIR / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    print(json.dumps({'account': ACCOUNT, 'filters': len(gmail.filters), 'brand_labels': len([name for name in gmail.labels if name.startswith(PREFIX + '/') and name.count('/') >= PREFIX.count('/') + 2]), 'inbox_messages_in_scope': len(gmail.list_ids('in:inbox ' + ELIGIBLE)), 'backfill_remaining': len(state.get('queue', [])), 'processed_total': state.get('processed', 0)}))


def preview(gmail, limit, snapshot_path):
    response = gmail.call('messages', params={'q': ELIGIBLE, 'maxResults': limit})
    messages = gmail.metadata([item['id'] for item in response.get('messages', [])])
    brands = load_brands()
    counts = defaultdict(int)
    for message in messages:
        labels = message.get('labelIds', [])
        sender = next((header['value'] for header in message.get('payload', {}).get('headers', []) if header['name'].lower() == 'from'), '')
        name, address = email.utils.parseaddr(sender)
        domain, brand = identify(name, address.lower(), brands)
        if brand:
            brands[domain] = brand
        category = next((item[1] for item in CATEGORIES if item[0] in labels), 'Otros')
        target = PREFIX + '/' + category + ('/' + brand if brand else ' + ' + PREFIX + '/Pendiente de marca')
        counts[target] += 1
    save(snapshot_path, {'account': ACCOUNT, 'sample': [{'id': item['id'], 'labels': item.get('labelIds', [])} for item in messages], 'filters': gmail.filters})
    print('VISTA PREVIA: no se han modificado mensajes, etiquetas ni filtros de Gmail.')
    print('Cuenta:', ACCOUNT)
    print('Alcance:', ELIGIBLE)
    for label, count in sorted(counts.items()):
        print(count, '->', label, '+ archivar; conservar estado de lectura')
    print('Muestra privada para verificar:', snapshot_path)


def remove_filters(gmail):
    path = STATE_DIR / 'owned-filters.json'
    owned = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    present = {item['id'] for item in gmail.filters}
    for filter_id in list(owned):
        if filter_id in present:
            gmail.call('settings/filters/' + filter_id, 'DELETE')
        owned.remove(filter_id)
        save(path, owned)
    print('Filtros creados por este perfil retirados. Mensajes y etiquetas conservados.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'auth', 'preview', 'bootstrap', 'sync', 'status', 'verify', 'remove-filters'])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--account', help='Tu cuenta; se usa solo con init')
    parser.add_argument('--credentials', help='Credenciales existentes; se usa solo con init')
    parser.add_argument('--client-secret', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--apply', action='store_true', help='Aplicar cambios al correo o a los filtros')
    parser.add_argument('--limit', type=int, default=150)
    args = parser.parse_args()
    if not 1 <= args.limit <= 250:
        parser.error('--limit must be between 1 and 250')
    if args.command == 'init':
        initialize(args.config.expanduser().resolve(), args.account, args.credentials)
        return
    configure(args.config.expanduser().resolve())
    if args.command == 'auth':
        authorize(args.client_secret)
        return
    if args.command in ('bootstrap', 'sync', 'remove-filters') and not args.apply:
        parser.error('Este comando modifica Gmail. Revisa preview y añade --apply para ejecutarlo.')
    snapshot_path = args.snapshot or STATE_DIR / 'sample.json'
    # Read-only checks do not block the scheduled maintenance job.
    if args.command in ('verify', 'status', 'preview'):
        gmail = Gmail()
        if args.command == 'verify':
            verify(gmail, snapshot_path)
        elif args.command == 'preview':
            preview(gmail, min(args.limit, 50), snapshot_path)
        else:
            status(gmail)
        return
    with maintenance_lock() as acquired:
        if not acquired:
            return
        gmail = Gmail()
        if args.command == 'bootstrap':
            bootstrap(gmail)
        elif args.command == 'sync':
            sync(gmail, args.limit)
        elif args.command == 'remove-filters':
            remove_filters(gmail)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('Error:', error)
        raise SystemExit(1)
