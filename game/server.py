"""Local multiplayer landmark game. Private round state never becomes static content."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse
import uuid

from model_bridge import ModelBridge, PLAYERS, MODEL_OPTIONS, MUSE, ProviderError, ROOT, safe_error, normalize_text

GAME = Path(__file__).resolve().parent
DATA = GAME / 'data'
STATIC = GAME / 'dist'
PORT = int(os.environ.get('PORT', '8770'))
ROUND_PHASES = ('awaiting_clue', 'creating_clue', 'checking_clue', 'rendering', 'guessing', 'ready_to_reveal', 'reveal', 'error')
ALIASES = {
    'golden-gate': ['Golden Gate', 'Golden Gate Bridge', 'Golden Gate Bridge San Francisco'],
    'painted-ladies': ['Painted Ladies', 'The Painted Ladies', 'Seven Sisters', 'Painted Ladies San Francisco'],
    'transamerica': ['Transamerica Pyramid', 'Transamerica Building', 'Transamerica Pyramid San Francisco'],
    'griffith': ['Griffith Observatory', 'Griffith Observatory Los Angeles'],
    'half-dome': ['Half Dome', 'Half Dome Yosemite'],
    'santa-monica': ['Santa Monica Pier', 'Santa Monica Pier California'],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return normalize_text(re.sub(r'^(?:the|an?)\s+', '', value.strip(), flags=re.IGNORECASE))


def is_correct(guess, target):
    return normalize(guess) in {normalize(name) for name in [target['name'], *target['aliases']]}


def load_locations():
    path = GAME / 'places.json'
    if path.exists():
        return json.loads(path.read_text())
    locations = json.loads((ROOT / 'experiments/california-levels/generation-summary.json').read_text())['locations']
    tiers = {'golden-gate': 1, 'painted-ladies': 2, 'transamerica': 2,
             'griffith': 3, 'half-dome': 3, 'santa-monica': 4}
    return [dict(row, country='California', difficulty=tiers[row['id']], aliases=ALIASES[row['id']])
            for row in locations]


def select_locations(locations, rounds):
    if len(locations) < rounds:
        raise ValueError('The landmark pool is smaller than the selected round count.')
    regions = list(dict.fromkeys(row.get('pool', row.get('country', row['region'])) for row in locations))
    random.SystemRandom().shuffle(regions)
    chosen = []
    for index in range(rounds):
        tier = 1 if rounds == 1 else ((index + 1) * 4 + rounds - 1) // rounds
        region = regions[index % len(regions)]
        remaining = [row for row in locations if row['id'] not in {item['id'] for item in chosen}]
        candidates = [row for row in remaining if row.get('pool', row.get('country', row['region'])) == region
                      and row.get('difficulty', 1) == tier]
        if not candidates:
            candidates = [row for row in remaining if row.get('difficulty', 1) == tier]
        if not candidates:
            candidates = sorted(remaining, key=lambda row: abs(row.get('difficulty', 1) - tier))[:1]
        chosen.append(random.SystemRandom().choice(candidates))
    return chosen


def custom_target(goal, difficulty):
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 120:
        raise ValueError('Enter a drawing goal with 1–120 characters.')
    name = goal.strip()
    return {'id': 'custom-' + uuid.uuid4().hex, 'name': name, 'aliases': [name],
            'region': '', 'country': '', 'pool': 'Custom', 'description': '',
            'custom': True, 'difficulty': difficulty}


class Cancelled(Exception):
    pass


class GameStore:
    def __init__(self, directory=DATA, bridge=None, renderer=None, recover=True, draw_seconds=60):
        self.draw_seconds = draw_seconds
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.bridge = bridge or ModelBridge()
        self.renderer = renderer or self.render
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.games = {}
        self.workers = {}
        self.locations = load_locations()
        if recover:
            for filename in sorted(self.directory.glob('*/state.json')):
                try:
                    state = json.loads(filename.read_text())
                    if state['status'] == 'running':
                        state['status'] = 'interrupted'
                        state['phase'] = 'error'
                        state['error'] = 'The server restarted during a round. Start a new match to continue.'
                    self.games[state['id']] = state
                except (ValueError, KeyError, OSError):
                    continue

    def save(self, state):
        target = self.directory / state['id']
        target.mkdir(mode=0o700, exist_ok=True)
        temporary = target / 'state.tmp'
        temporary.write_text(json.dumps(state, indent=2))
        temporary.chmod(0o600)
        temporary.replace(target / 'state.json')

    def event(self, state, message):
        state['events'].append({'at': now(), 'message': message})
        state['updatedAt'] = now()

    def public(self, state):
        public = {key: deepcopy(state[key]) for key in (
            'id', 'status', 'phase', 'roundIndex', 'totalRounds', 'players', 'events', 'cost', 'createdAt', 'updatedAt')}
        public['artist'] = deepcopy(state.get('artist', MUSE))
        if state.get('error'):
            public['error'] = state['error']
        public['rounds'] = []
        for row in state['rounds'][:state['roundIndex'] + 1]:
            out = {key: deepcopy(row[key]) for key in ('number', 'drawerId', 'status', 'timings')}
            out['describerId'] = row.get('describerId', row['drawerId'])
            out['difficulty'] = row.get('difficulty', row['_target'].get('difficulty', 1))
            for key in ('error',):
                if key in row:
                    out[key] = deepcopy(row[key])
            if row.get('_imageReady'):
                out['imageUrl'] = f"/api/games/{state['id']}/rounds/{row['number']}/image?v={row.get('_imageVersion', 1)}"
            if row.get('_revealed'):
                for key in ('clue', 'validator'):
                    if key in row:
                        out[key] = deepcopy(row[key])
                out.update(answer=row['_target']['name'], region=row['_target']['region'],
                           country=row['_target'].get('country'), pool=row['_target'].get('pool'),
                           guesses=deepcopy(row['_guesses']),
                           awards=deepcopy(row['awards']))
            remaining = row.get('_drawRemaining', self.draw_seconds)
            if row.get('_drawClock') is not None:
                remaining = max(0, remaining - (time.monotonic() - row['_drawClock']))
            drawing_active = row['status'] in ('awaiting_clue', 'creating_clue', 'checking_clue', 'rendering')
            out['drawing'] = {'limitSeconds': self.draw_seconds, 'secondsRemaining': round(remaining, 1),
                              'paused': row['status'] != 'awaiting_clue',
                              'canFinish': drawing_active and bool(row.get('_imageReady')) and row['status'] == 'awaiting_clue' and not row.get('_finishDrawing'),
                              'version': row.get('_imageVersion', 0),
                              'attempts': [{'number': index + 1, 'verdict': item['verdict']['verdict'],
                                            'status': item.get('status', item['verdict']['verdict']),
                                            'seconds': item.get('seconds', 0)}
                                           for index, item in enumerate(row.get('_clueAttempts', []))]}
            out['promptAttempts'] = deepcopy(row.get('_clueAttempts', []))
            out['submittedPlayerIds'] = list(row.get('_submittedPlayerIds', []))
            out['calls'] = deepcopy(row.get('calls', []))
            public['rounds'].append(out)
        return public

    def invitations(self, state):
        return [{'playerId': player['id'], 'name': player['name'],
                 'token': state['_seatTokens'][player['id']]}
                for player in state['players'] if player.get('type') == 'human']

    def view(self, state, token=None):
        result = self.public(state)
        host_token = state.get('_hostToken')
        if token and host_token and secrets.compare_digest(token, host_token):
            result['hostView'] = True
            result['invitations'] = self.invitations(state)
        else:
            result['hostView'] = not host_token
        for player_id, seat_token in state.get('_seatTokens', {}).items():
            if token and secrets.compare_digest(token, seat_token):
                player = next(player for player in state['players'] if player['id'] == player_id)
                result['viewer'] = {'playerId': player_id, 'name': player['name'], 'type': 'human'}
                row = state['rounds'][state['roundIndex']]
                if row['drawerId'] == player_id and state['phase'] in ('awaiting_clue', 'checking_clue', 'rendering') and state['status'] == 'running':
                    result['privateAssignment'] = {'name': row['_target']['name'], 'canChangeGoal': not row.get('_clueAttempts') and '_humanClue' not in row}
                    if row.get('_humanFeedback'):
                        result['privateFeedback'] = row['_humanFeedback']
                break
        return result

    def get(self, identifier=None, token=None):
        with self.lock:
            if identifier is None:
                state = max(self.games.values(), key=lambda value: value['createdAt'], default=None)
            else:
                state = self.games.get(identifier)
            return self.view(state, token) if state else None

    def roster(self, players):
        if players is None:
            return [dict(player, type='ai', score=0) for player in PLAYERS]
        if not isinstance(players, list) or not 2 <= len(players) <= 6:
            raise ValueError('Choose between two and six players.')
        options = {option['id']: option for option in MODEL_OPTIONS}
        models = {option['model']: option for option in MODEL_OPTIONS}
        result = []
        seen = set()
        for selected in players:
            if not isinstance(selected, dict):
                raise ValueError('Each player must be a seat object.')
            identifier = selected.get('id')
            if identifier not in {*options, 'person-1', 'person-2'} or identifier in seen:
                raise ValueError('Choose unique supported player seats.')
            seen.add(identifier)
            kind = selected.get('type', 'human' if identifier.startswith('person-') else 'ai')
            if kind not in ('ai', 'human') or (identifier.startswith('person-') and kind != 'human'):
                raise ValueError('Each seat must be an AI model or a person.')
            base = options.get(identifier, {'id': identifier, 'name': 'Player', 'model': None, 'provider': 'Human'})
            if kind == 'ai':
                model = selected.get('model', base['model'])
                if model not in models:
                    raise ValueError('Choose a registered AI player model.')
                base = dict(base, model=model, provider=models[model]['provider'])
            name = selected.get('name', base['name'])
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 24 or any(ord(char) < 32 for char in name):
                raise ValueError('Player names must contain 1–24 printable characters.')
            result.append(dict(base, id=identifier, name=name.strip(), type=kind, score=0,
                               model=base['model'] if kind == 'ai' else None,
                               provider=base['provider'] if kind == 'ai' else 'Human'))
        return result

    def create(self, rounds=None, players=None, custom_goals=None, demo_route=False):
        roster = self.roster(players)
        if type(demo_route) is not bool:
            raise ValueError('demoRoute must be true or false.')
        if demo_route:
            rounds = 3
        if rounds is None:
            rounds = len(roster)
        if type(rounds) is not int or not 1 <= rounds <= 8:
            raise ValueError('Choose between one and eight rounds.')
        if custom_goals is None:
            custom_goals = []
        if not isinstance(custom_goals, list) or len(custom_goals) > rounds:
            raise ValueError('Provide at most one custom drawing goal per round.')
        if any(not isinstance(goal, str) or len(goal.strip()) > 120 for goal in custom_goals):
            raise ValueError('Drawing goals must be strings of at most 120 characters.')
        if demo_route and any(goal.strip() for goal in custom_goals):
            raise ValueError('The competition route uses its three selected landmarks.')
        with self.lock:
            if any(state['status'] in ('running', 'awaiting_reveal', 'awaiting_next') for state in self.games.values()):
                raise ValueError('A match is already active. Finish or stop it before starting another.')
            identifier = uuid.uuid4().hex
            if demo_route:
                by_id = {target['id']: target for target in self.locations}
                targets = [deepcopy(by_id[identifier]) for identifier in
                           ('painted-ladies', 'borgund', 'rani-mahal')]
            else:
                targets = select_locations(self.locations, rounds)
            for index, goal in enumerate(custom_goals):
                if goal.strip():
                    targets[index] = custom_target(goal, targets[index].get('difficulty', 1))
            host_token = secrets.token_urlsafe(32)
            state = {'id': identifier, 'status': 'running', 'phase': 'creating_clue', 'roundIndex': 0,
                     'totalRounds': rounds, 'createdAt': now(), 'updatedAt': now(), 'artist': MUSE,
                     'players': roster, 'events': [], '_hostToken': host_token,
                     '_seatTokens': {player['id']: secrets.token_urlsafe(32)
                                     for player in roster if player['type'] == 'human'},
                     'cost': {'openrouterUsd': 0.0, 'codexCalls': 0, 'codexUsd': None,
                              'note': 'OpenRouter-reported API cost. Codex subscription debit is not available.'},
                     'rounds': [{'number': index + 1, 'drawerId': roster[index % len(roster)]['id'],
                                 'describerId': roster[index % len(roster)]['id'],
                                 'difficulty': target.get('difficulty', 1), 'status': 'pending',
                                 'timings': {}, 'calls': [], '_target': target, '_guesses': []}
                                for index, target in enumerate(targets)]}
            self.games[identifier] = state
            self.event(state, 'Match started. Muse checks each draw prompt and creates its image.')
            self.save(state)
            self.start_worker(identifier)
            result = self.view(state, host_token)
            result['hostToken'] = host_token
            return result

    def require_host(self, state, token):
        host_token = state.get('_hostToken')
        if host_token and (not token or not secrets.compare_digest(host_token, token)):
            raise PermissionError('Only the host can control this match.')

    def human_seat(self, state, token):
        for player_id, seat_token in state.get('_seatTokens', {}).items():
            if token and secrets.compare_digest(seat_token, token):
                return player_id
        raise PermissionError('Use your private player link to submit a turn.')

    def set_goal(self, identifier, goal, token):
        with self.lock:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            row = state['rounds'][state['roundIndex']]
            host_token = state.get('_hostToken')
            is_host = bool(host_token and token and secrets.compare_digest(host_token, token))
            if not is_host:
                player_id = self.human_seat(state, token)
                if player_id != row['drawerId']:
                    raise PermissionError('Only the current describer or host can choose this goal.')
            if state['status'] != 'running' or state['phase'] != 'awaiting_clue' or row.get('_goalLocked'):
                raise ValueError('The goal can change only before the first description is submitted.')
            row['_target'] = custom_target(goal, row.get('difficulty', 1))
            row.pop('_humanFeedback', None)
            self.event(state, 'The private drawing goal was updated before the description.')
            self.save(state)
            return self.view(state, token)

    def submit_clue(self, identifier, clue, token):
        with self.condition:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            player_id = self.human_seat(state, token)
            row = state['rounds'][state['roundIndex']]
            if state['status'] != 'running' or state['phase'] != 'awaiting_clue' or row['drawerId'] != player_id:
                raise ValueError('This seat is not waiting for a description.')
            if not isinstance(clue, str) or not 1 <= len(clue.strip()) <= 1600:
                raise ValueError('Enter a description with 1–1600 characters.')
            remaining = row.get('_drawRemaining', self.draw_seconds)
            if row.get('_drawClock') is not None:
                remaining -= time.monotonic() - row['_drawClock']
            if row.get('_finishDrawing') or (row.get('_imageReady') and remaining <= 0):
                self.condition.notify_all()
                raise ValueError('Drawing time is over. The latest usable drawing is locked.')
            if '_humanClue' in row:
                raise ValueError('Your description is already being checked.')
            self.pause_drawing_clock(row)
            row['_goalLocked'] = True
            row['_humanClue'] = clue.strip()
            row.pop('_humanFeedback', None)
            state['phase'] = row['status'] = 'checking_clue'
            self.save(state)
            self.condition.notify_all()
            return self.view(state, token)

    def submit_guess(self, identifier, guess, token):
        with self.condition:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            player_id = self.human_seat(state, token)
            row = state['rounds'][state['roundIndex']]
            if state['status'] != 'running' or state['phase'] != 'guessing' or row['drawerId'] == player_id:
                raise ValueError('This seat is not waiting for a guess.')
            if not isinstance(guess, str) or not 1 <= len(guess.strip()) <= 200:
                raise ValueError('Enter one landmark name with 1–200 characters.')
            answers = row.setdefault('_humanGuesses', {})
            if player_id in answers:
                raise ValueError('Your guess is already locked.')
            answers[player_id] = guess.strip()
            row.setdefault('_submittedPlayerIds', []).append(player_id)
            self.save(state)
            self.condition.notify_all()
            return self.view(state, token)

    def pause_drawing_clock(self, row):
        clock = row.pop('_drawClock', None)
        if clock is not None:
            row['_drawRemaining'] = max(0, row.get('_drawRemaining', self.draw_seconds) - (time.monotonic() - clock))

    def finish_drawing(self, identifier, token):
        with self.condition:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            row = state['rounds'][state['roundIndex']]
            host_token = state.get('_hostToken')
            is_host = bool(host_token and token and secrets.compare_digest(token, host_token))
            if not is_host and self.human_seat(state, token) != row['drawerId']:
                raise PermissionError('Only the describer or host can finish this drawing.')
            if state['status'] != 'running' or state['phase'] != 'awaiting_clue' or not row.get('_imageReady'):
                raise ValueError('Wait for a usable drawing before starting the guesses.')
            self.pause_drawing_clock(row)
            row['_finishDrawing'] = True
            self.event(state, 'The drawing is locked. Guessing starts with the latest usable version.')
            self.save(state)
            self.condition.notify_all()
            return self.view(state, token)

    def wait_for_human_clue(self, state, row, drawer):
        self.phase(state, row, 'awaiting_clue',
                   f"{drawer['name']} can refine the drawing." if row.get('_imageReady') else
                   f"{drawer['name']} is writing a private description.")
        with self.condition:
            row.setdefault('_drawRemaining', self.draw_seconds)
            row['_drawClock'] = time.monotonic()
            while '_humanClue' not in row:
                self.check(state)
                remaining = max(0, row['_drawRemaining'] - (time.monotonic() - row.get('_drawClock', time.monotonic())))
                if row.get('_finishDrawing') or (remaining <= 0 and row.get('_imageReady')):
                    self.pause_drawing_clock(row)
                    row['_finishDrawing'] = True
                    return None
                # No usable image yet: do not dead-end the match when the first prompt is late.
                self.condition.wait(timeout=max(.05, remaining) if remaining > 0 else None)
            self.check(state)
            self.pause_drawing_clock(row)
            return row.pop('_humanClue')

    def wait_for_human_guess(self, state, row, player_id):
        with self.condition:
            while player_id not in row.get('_humanGuesses', {}):
                self.check(state)
                if row.get('_guessFailure'):
                    raise ProviderError(row['_guessFailure'])
                self.condition.wait()
            self.check(state)
            return row['_humanGuesses'][player_id]

    def start_worker(self, identifier):
        worker = threading.Thread(target=self.run_round, args=(identifier,), daemon=True)
        self.workers[identifier] = worker
        worker.start()

    def check(self, state):
        if state['status'] == 'cancelled':
            raise Cancelled()

    def phase(self, state, row, phase, message):
        with self.lock:
            self.check(state)
            state['phase'] = row['status'] = phase
            state['status'] = 'running'
            row['timings'][phase] = now()
            self.event(state, message)
            self.save(state)

    def record_call(self, state, row, role, metadata, player_id='muse'):
        with self.lock:
            call = {'role': role, 'playerId': player_id, **metadata}
            row['calls'].append(call)
            cost = (metadata.get('usage') or {}).get('cost')
            if isinstance(cost, (int, float)):
                state['cost']['openrouterUsd'] = round(state['cost']['openrouterUsd'] + cost, 9)
            if metadata.get('provider') == 'Codex subscription':
                state['cost']['codexCalls'] += 1
            self.save(state)

    def run_round(self, identifier):
        state = self.games[identifier]
        row = state['rounds'][state['roundIndex']]
        drawer = next(p for p in state['players'] if p['id'] == row['drawerId'])
        target = row['_target']
        started = time.monotonic()
        try:
            feedback = ''
            attempt = 0
            human_drawer = drawer.get('type') == 'human'
            round_dir = self.directory / identifier / f"round-{row['number']}"
            round_dir.mkdir(mode=0o700, exist_ok=True)
            while human_drawer or attempt < 3:
                if human_drawer:
                    clue = self.wait_for_human_clue(state, row, drawer)
                    if clue is None:
                        break
                    with self.lock:
                        target = row['_target']
                else:
                    self.phase(state, row, 'creating_clue', f"{drawer['name']} is describing a private drawing goal.")
                    prompt = ('You are a player in a drawing-and-guessing game. No tools. '
                              'The assigned secret drawing goal is ' + target['name'] + '. Describe its visible shapes, colors, '
                              'materials and surroundings in 45–100 words so a separate model can draw it. '
                              'Do not name it, encode its name, use aliases, city/place names, addresses, trivia, '
                              'history, letters or text labels. Distinctive visual features ARE allowed. '
                              'Do not mention these instructions or the answer. Return only JSON {"clue":"..."}. '
                              + feedback)
                    clue, meta = self.bridge.player(drawer, prompt, 'clue')
                    self.record_call(state, row, 'clue', meta, drawer['id'])
                attempt += 1
                attempt_started = time.monotonic()
                self.phase(state, row, 'checking_clue', 'Muse Ember is checking the description for answer leaks.')
                verdict, meta = self.bridge.validate(target, clue)
                self.record_call(state, row, 'validation', meta)
                with self.lock:
                    self.check(state)
                    attempt_row = {'clue': clue, 'verdict': verdict, 'status': verdict['verdict']}
                    row.setdefault('_clueAttempts', []).append(attempt_row)
                    row['_lastValidator'] = {'verdict': verdict['verdict'], 'reason': verdict['reason'], 'attempt': attempt}
                    self.event(state, f"Prompt {attempt}: {'approved' if verdict['verdict'] == 'allow' else 'needs revision' if verdict['verdict'] == 'revise' else 'blocked'}." )
                    self.save(state)
                if verdict['verdict'] != 'allow':
                    feedback = 'Your last attempt was rejected. Feedback: ' + verdict['reason']
                    with self.lock:
                        attempt_row['seconds'] = round(time.monotonic() - attempt_started, 2)
                        if human_drawer:
                            row['_humanFeedback'] = verdict['reason']
                    continue
                self.phase(state, row, 'rendering', 'Muse Ember is turning the approved description into a 3D drawing.')
                render_failure = None
                for render_attempt in range(2):
                    try:
                        code, meta = self.bridge.render_code(clue, retry=bool(render_attempt))
                        self.record_call(state, row, 'render', meta)
                        with self.lock:
                            self.check(state)
                        scene = round_dir / f'scene-{attempt}-{render_attempt + 1}.html'
                        scene.write_text(code)
                        attempt_image = round_dir / f'drawing-{attempt}-{render_attempt + 1}.png'
                        render_meta = self.renderer(scene, attempt_image)
                        with self.lock:
                            self.check(state)
                            self.event(state, 'Muse Ember is checking that the main subject is visible.')
                            self.save(state)
                        review, review_meta = self.bridge.review_image(attempt_image)
                        self.record_call(state, row, 'visual_review', review_meta)
                        with self.lock:
                            self.check(state)
                            row.setdefault('_visualReviews', []).append({'attempt': attempt, 'renderAttempt': render_attempt + 1, **review})
                            self.save(state)
                        if not review['usable']:
                            raise ProviderError('The drawing did not pass the subject visibility check.')
                        with self.lock:
                            shutil.copyfile(attempt_image, round_dir / 'drawing.next.png')
                            (round_dir / 'drawing.next.png').replace(round_dir / 'drawing.png')
                            row['_render'] = render_meta
                            row['_imageReady'] = True
                            row['_imageVersion'] = row.get('_imageVersion', 0) + 1
                            row['clue'] = clue
                            row['validator'] = row['_lastValidator']
                            row.pop('_humanFeedback', None)
                            attempt_row['status'] = 'drawn'
                            attempt_row['seconds'] = round(time.monotonic() - attempt_started, 2)
                            self.event(state, f"Drawing version {row['_imageVersion']} is ready." )
                            self.save(state)
                        render_failure = None
                        break
                    except ProviderError as exc:
                        render_failure = exc
                        if getattr(exc, 'metadata', None):
                            self.record_call(state, row, 'failed_render', exc.metadata)
                            exc.metadata = None
                        if not render_attempt:
                            with self.lock:
                                self.check(state)
                                self.event(state, 'The drawing failed a render or visibility check. Muse Ember is trying a clearer view.')
                                self.save(state)
                if render_failure:
                    with self.lock:
                        attempt_row['status'] = 'render_failed'
                        attempt_row['seconds'] = round(time.monotonic() - attempt_started, 2)
                        if human_drawer:
                            row['_humanFeedback'] = ('This revision could not be drawn. Your previous drawing is still available; revise again or finish.' if row.get('_imageReady') else 'This prompt could not be drawn. Try a clearer description of the main shapes.')
                            self.event(state, 'The revision failed. The previous usable drawing was kept.' if row.get('_imageReady') else 'The drawing failed. The describer can revise the prompt.')
                        else:
                            raise render_failure
                if not human_drawer:
                    break
            else:
                raise ProviderError('No valid physical description after three attempts. This round cannot continue.')
            if not row.get('_imageReady'):
                raise ProviderError('No usable drawing is available yet.')
            self.phase(state, row, 'guessing', 'The other players are looking at the drawing independently.')
            image = round_dir / 'drawing.png'
            context = ('Identify the depicted landmark, place, or object from the attached drawing. '
                       if target.get('custom') else
                       'Identify the depicted landmark in California, Norway or Nepal from the attached drawing. ')
            prompt = (context + 'Use only what is visible in the image. No tools or internet. Give ONE specific name. '
                      'Do not give alternatives or include its city. Return JSON with your guess and a brief explanation of visible evidence.')
            guessers = [p for p in state['players'] if p['id'] != drawer['id']]
            def guess(player):
                explanation = None
                if player.get('type') == 'human':
                    answer = self.wait_for_human_guess(state, row, player['id'])
                else:
                    answer, meta = self.bridge.player(player, prompt, 'guess', image=image)
                    explanation = meta.pop('explanation', None)
                    self.record_call(state, row, 'guess', meta, player['id'])
                    with self.lock:
                        self.check(state)
                        row.setdefault('_submittedPlayerIds', []).append(player['id'])
                        self.save(state)
                return {'playerId': player['id'], 'name': player['name'], 'guess': answer,
                        'correct': is_correct(answer, target), 'explanation': explanation}
            def wake_after_failure(future):
                error = future.exception()
                if error:
                    with self.condition:
                        row['_guessFailure'] = safe_error(error)
                        self.condition.notify_all()
            with ThreadPoolExecutor(max_workers=len(guessers)) as pool:
                futures = [pool.submit(guess, player) for player in guessers]
                for future in futures:
                    future.add_done_callback(wake_after_failure)
                guesses = [future.result() for future in futures]
            with self.lock:
                self.check(state)
                row['_guesses'] = guesses
                row['timings']['elapsedSeconds'] = round(time.monotonic() - started, 2)
                row['status'] = state['phase'] = 'ready_to_reveal'
                state['status'] = 'awaiting_reveal'
                self.event(state, 'All guesses are locked. The round is ready to score.')
                self.save(state)
        except Cancelled:
            return
        except Exception as exc:
            with self.lock:
                if getattr(exc, 'metadata', None):
                    self.record_call(state, row, 'failed_' + state['phase'], exc.metadata)
                if state['status'] == 'cancelled':
                    return
                row['status'] = state['phase'] = 'error'
                state['status'] = 'error'
                row['error'] = state['error'] = safe_error(exc)
                self.event(state, 'This round stopped before scoring. No points were awarded.')
                self.save(state)

    def reveal(self, identifier, token=None):
        with self.lock:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            self.require_host(state, token)
            if state['status'] != 'awaiting_reveal':
                raise ValueError('The guesses are not ready to reveal.')
            row = state['rounds'][state['roundIndex']]
            awards = {p['id']: 0 for p in state['players']}
            for guess in row['_guesses']:
                if guess['correct']:
                    awards[guess['playerId']] = 2
            if any(awards.values()):
                awards[row['drawerId']] = 2
            for player in state['players']:
                player['score'] += awards[player['id']]
            row['awards'] = awards
            row['_revealed'] = True
            row['status'] = state['phase'] = 'reveal'
            state['status'] = 'awaiting_next'
            self.event(state, 'Answer revealed and points awarded.')
            self.save(state)
            return self.view(state, token)

    def next(self, identifier, token=None):
        with self.lock:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            self.require_host(state, token)
            if state['status'] != 'awaiting_next':
                raise ValueError('Reveal the current round before continuing.')
            if state['roundIndex'] + 1 >= state['totalRounds']:
                state['status'] = state['phase'] = 'complete'
                self.event(state, 'Match complete. The highest score wins; equal scores share the win.')
                self.save(state)
            else:
                state['roundIndex'] += 1
                state['status'] = 'running'
                state['phase'] = 'creating_clue'
                self.save(state)
                self.start_worker(identifier)
            return self.view(state, token)

    def cancel(self, identifier, token=None):
        with self.lock:
            state = self.games.get(identifier)
            if not state:
                raise KeyError('Match not found.')
            self.require_host(state, token)
            if state['status'] in ('complete', 'cancelled'):
                return self.view(state, token)
            state['status'] = state['phase'] = 'cancelled'
            self.event(state, 'Match stopped. Any in-flight provider request may still finish and be billed.')
            self.save(state)
            self.condition.notify_all()
            return self.view(state, token)

    def image(self, identifier, number):
        with self.lock:
            state = self.games.get(identifier)
            if not state or number < 1 or number > len(state['rounds']):
                return None
            if not state['rounds'][number - 1].get('_imageReady'):
                return None
            return self.directory / identifier / f'round-{number}' / 'drawing.png'

    def render(self, source, output):
        env = {key: value for key, value in os.environ.items()
               if 'KEY' not in key.upper() and 'TOKEN' not in key.upper() and 'SECRET' not in key.upper()}
        try:
            result = subprocess.run(['node', str(GAME / 'render_scene.cjs'), str(source), str(output),
                                     str(ROOT / 'experiments/california-levels')],
                                    text=True, capture_output=True, env=env, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise ProviderError('The drawing renderer exceeded its 60-second limit.') from exc
        if result.returncode:
            raise ProviderError('The generated drawing failed browser validation.')
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise ProviderError('The renderer returned invalid metadata.') from exc


class Handler(BaseHTTPRequestHandler):
    server_version = 'LandmarkGame/1.0'

    @property
    def store(self):
        return self.server.store

    def log_message(self, format, *args):
        # Request paths contain game IDs only; do not print POST bodies or headers.
        pass

    def send_json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type=None):
        if not path or not path.is_file():
            self.send_json(404, {'error': 'Not found.'})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type or mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def token(self):
        authorization = self.headers.get('Authorization', '')
        if authorization.startswith('Bearer '):
            return authorization[7:]
        return None

    def valid_host(self):
        host = self.headers.get('Host', '')
        return host in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.valid_host():
            self.send_json(403, {'error': 'Local host only.'}); return
        path = urlparse(self.path).path
        if path == '/api/health':
            caps = self.store.bridge.capabilities()
            models = [{**p, 'available': caps['openrouterConfigured'] if p['provider'] == 'OpenRouter' else caps['codexInstalled']}
                      for p in MODEL_OPTIONS]
            self.send_json(200, {'ready': all(p['available'] for p in models), 'models': models, **caps})
        elif path == '/api/games/latest':
            self.send_json(200, {'game': self.store.get(token=self.token())})
        elif re.fullmatch(r'/api/games/[0-9a-f]{32}', path):
            state = self.store.get(path.rsplit('/', 1)[1], self.token())
            self.send_json(200 if state else 404, {'game': state} if state else {'error': 'Match not found.'})
        elif match := re.fullmatch(r'/api/games/([0-9a-f]{32})/rounds/(\d+)/image', path):
            self.send_file(self.store.image(match[1], int(match[2])), 'image/png')
        elif path.startswith('/api/'):
            self.send_json(404, {'error': 'Not found.'})
        else:
            relative = path.lstrip('/') or 'index.html'
            candidate = (STATIC / relative).resolve()
            if not candidate.is_relative_to(STATIC.resolve()):
                self.send_json(404, {'error': 'Not found.'}); return
            if not candidate.exists() and '.' not in Path(relative).name:
                candidate = STATIC / 'index.html'
            self.send_file(candidate)

    def do_POST(self):
        if not self.valid_host():
            self.send_json(403, {'error': 'Local host only.'}); return
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            self.send_json(403, {'error': 'Cross-origin requests are not allowed.'}); return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send_json(415, {'error': 'Use application/json.'}); return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > 8192:
                raise ValueError('Request is too large.')
            payload = json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(payload, dict):
                raise ValueError('Use a JSON object.')
            path = urlparse(self.path).path
            if path == '/api/games':
                game = self.store.create(payload.get('rounds'), payload.get('players'), payload.get('customGoals'), payload.get('demoRoute', False))
                host_token = game.pop('hostToken')
                self.send_json(201, {'game': game, 'hostToken': host_token, 'invitations': game['invitations']})
            elif match := re.fullmatch(r'/api/games/([0-9a-f]{32})/(next|reveal|cancel)', path):
                self.send_json(200, {'game': getattr(self.store, match[2])(match[1], self.token())})
            elif match := re.fullmatch(r'/api/games/([0-9a-f]{32})/finish-drawing', path):
                self.send_json(200, {'game': self.store.finish_drawing(match[1], self.token())})
            elif match := re.fullmatch(r'/api/games/([0-9a-f]{32})/goal', path):
                self.send_json(200, {'game': self.store.set_goal(match[1], payload.get('goal'), self.token())})
            elif match := re.fullmatch(r'/api/games/([0-9a-f]{32})/(clue|guess)', path):
                method = self.store.submit_clue if match[2] == 'clue' else self.store.submit_guess
                self.send_json(200, {'game': method(match[1], payload.get(match[2]), self.token())})
            else:
                self.send_json(404, {'error': 'Not found.'})
        except PermissionError as exc:
            self.send_json(403, {'error': str(exc)})
        except KeyError as exc:
            self.send_json(404, {'error': str(exc)})
        except (ValueError, TypeError) as exc:
            self.send_json(409, {'error': safe_error(exc)})
        except Exception:
            self.send_json(500, {'error': 'The request could not be completed.'})


def main():
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    server.store = GameStore()
    print(f'Landmark game running at http://127.0.0.1:{PORT}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
