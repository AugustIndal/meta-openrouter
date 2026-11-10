"""Offline checks for player isolation, explicit reveal, scoring and transitions."""
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from model_bridge import ModelBridge, ProviderError, normalize_text
from server import GameStore, is_correct, select_locations

class Bridge:
    def __init__(self, block_first=False):
        self.calls = []
        self.checks = 0
        self.block_first = block_first
        self.known = {}
    def player(self, player, prompt, field, image=None):
        self.calls.append((player['id'], field, prompt, image))
        if field == 'clue':
            # Extract assignment only inside test provider.
            target = prompt.split('The assigned secret drawing goal is ',1)[1].split('. Describe',1)[0]
            self.known['target'] = target
            return 'A tall pale building with a pointed top and visible dark windows.', {'provider': 'Codex subscription', 'usage': {}}
        return self.known['target'], {'provider': 'Codex subscription', 'usage': {}}
    def validate(self, target, clue):
        self.known["target"] = target["name"]
        self.checks += 1
        verdict = 'block' if self.block_first and self.checks == 1 else 'allow'
        return {'verdict':verdict, 'reason':'Describe only visible features.'}, {'provider':'Meta', 'usage':{'cost':.001}}
    def render_code(self, clue, retry=False):
        return '<html>scene</html>', {'provider':'Meta', 'usage':{'cost':.01}}

    def review_image(self, image):
        return {'usable':True, 'reason':'The main subject is visible.'}, {'provider':'Meta', 'usage':{'cost':.001}}


def renderer(source, output):
    output.write_bytes(b'fake png')
    return {'width':1200,'height':800}


def wait_for(store, phase):
    for _ in range(200):
        state = store.get()
        if state['phase'] == phase:
            return state
        if state['phase'] == 'error':
            raise AssertionError(state['error'])
        time.sleep(.01)
    raise AssertionError('Timed out waiting for '+phase)


class GameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = Bridge()
        self.store = GameStore(self.temp.name, self.bridge, renderer, draw_seconds=0)
    def host_token(self):
        return next(iter(self.store.games.values()))["_hostToken"]
    def tearDown(self):
        self.temp.cleanup()
    def test_private_answers_and_atomic_reveal(self):
        created = self.store.create()
        state = wait_for(self.store,'ready_to_reveal')
        current = state['rounds'][0]
        self.assertNotIn('answer',current)
        self.assertNotIn('clue',current)
        self.assertNotIn('validator',current)
        self.assertEqual(len(state['rounds']),1)
        self.assertNotIn('guesses',current)
        self.assertNotIn('_target',json.dumps(state))
        self.assertIn('imageUrl',current)
        self.assertTrue(all(p['score']==0 for p in state['players']))
        self.assertEqual(state['cost']['openrouterUsd'],.012)
        for _, field, prompt, image in self.bridge.calls:
            if field == 'guess':
                self.assertNotIn('assigned secret',prompt)
                self.assertNotIn(self.bridge.known['target'],prompt)
                self.assertNotIn('A tall pale building',prompt)
                self.assertEqual(Path(image).name,'drawing.png')
        state = self.store.reveal(created['id'], self.host_token())
        self.assertTrue(all(p['score']==2 for p in state['players']))
        self.assertTrue(all(g['correct'] for g in state['rounds'][0]['guesses']))
        self.assertIn('clue',state['rounds'][0])
        self.assertIn('validator',state['rounds'][0])
        with self.assertRaises(ValueError): self.store.reveal(created['id'], self.host_token())
        self.assertTrue(all(p['score']==2 for p in self.store.get()['players']))
    def test_three_round_match_and_no_duplicate_next(self):
        state = self.store.create(rounds=3)
        with self.assertRaises(ValueError): self.store.create()
        with self.assertRaises(ValueError): self.store.next(state['id'], self.host_token())
        for round_no in range(3):
            wait_for(self.store,'ready_to_reveal')
            state = self.store.reveal(state['id'], self.host_token())
            state = self.store.next(state['id'], self.host_token())
        self.assertEqual(state['status'],'complete')
        self.assertEqual([p['score'] for p in state['players']],[6,6,6,6])
    def test_revise_tries_again_without_publishing_rejected_text(self):
        self.bridge.block_first=True
        self.store.create()
        state=wait_for(self.store,'ready_to_reveal')
        self.assertEqual(self.bridge.checks,2)
        revealed=self.store.reveal(state['id'], self.host_token())
        self.assertEqual(revealed['rounds'][0]['validator']['attempt'],2)
        self.assertNotIn('_clueAttempts',json.dumps(state))
    def test_cancel_while_call_inflight_stops_dependent_work(self):
        gate = threading.Event()
        original = self.bridge.player
        def paused(*args,**kwargs):
            gate.wait(2)
            return original(*args,**kwargs)
        self.bridge.player=paused
        state=self.store.create()
        state=self.store.cancel(state['id'], self.host_token())
        gate.set()
        self.store.workers[state['id']].join(2)
        self.assertEqual(self.store.get()['phase'],'cancelled')
        self.assertEqual(self.bridge.checks,0)
    def test_recovery_never_replays_paid_calls(self):
        state=self.store.create()
        wait_for(self.store,'ready_to_reveal')
        other=GameStore(self.temp.name, Bridge(), renderer)
        self.assertEqual(other.get()['status'],'awaiting_reveal')
        self.assertEqual(other.workers,{})
    def human_roster(self):
        return [{'id': seat, 'type': 'human', 'name': name}
                for seat, name in [('luna', 'Alice'), ('terra', 'Bob'), ('sonnet', 'Carol')]]
    def test_human_assignment_seat_authorization_and_guess_secrecy(self):
        created = self.store.create(players=self.human_roster())
        state = wait_for(self.store, 'awaiting_clue')
        tokens = {row['playerId']: row['token'] for row in created['invitations']}
        drawer = self.store.get(state['id'], tokens['luna'])
        other = self.store.get(state['id'], tokens['terra'])
        host = self.store.get(state['id'], created['hostToken'])
        self.assertIn('privateAssignment', drawer)
        self.assertNotIn('privateAssignment', other)
        self.assertNotIn('privateAssignment', host)
        self.assertNotIn('invitations', state)
        self.assertNotIn('hostToken', state)
        with self.assertRaises(PermissionError):
            self.store.submit_clue(state['id'], 'A tower.', created['hostToken'])
        with self.assertRaises(ValueError):
            self.store.submit_clue(state['id'], 'A tower.', tokens['terra'])
        with self.assertRaises(PermissionError):
            self.store.cancel(state['id'], tokens['luna'])
        self.store.submit_clue(state['id'], 'A pale pointed tower with dark windows.', tokens['luna'])
        state = wait_for(self.store, 'guessing')
        answer = drawer['privateAssignment']['name']
        self.assertNotIn('privateAssignment', self.store.get(state['id'], tokens['luna']))
        self.store.submit_guess(state['id'], answer, tokens['terra'])
        state = self.store.get(state['id'])
        self.assertEqual(state['rounds'][0]['submittedPlayerIds'], ['terra'])
        self.assertNotIn('guesses', state['rounds'][0])
        with self.assertRaises(ValueError):
            self.store.submit_guess(state['id'], answer, tokens['terra'])
        self.store.submit_guess(state['id'], answer, tokens['sonnet'])
        wait_for(self.store, 'ready_to_reveal')
        self.assertEqual(self.bridge.calls, [])
        revealed = self.store.reveal(state['id'], created['hostToken'])
        self.assertEqual([player['score'] for player in revealed['players']], [2, 2, 2])
    def test_human_rejected_clue_can_resubmit_and_cancel_wakes_wait(self):
        self.bridge.block_first = True
        created = self.store.create(players=self.human_roster())
        wait_for(self.store, 'awaiting_clue')
        tokens = {row['playerId']: row['token'] for row in created['invitations']}
        self.store.submit_clue(created['id'], 'A tower.', tokens['luna'])
        wait_for(self.store, 'awaiting_clue')
        drawer = self.store.get(created['id'], tokens['luna'])
        self.assertIn('privateFeedback', drawer)
        self.assertNotIn('privateFeedback', self.store.get(created['id'], tokens['terra']))
        self.store.submit_clue(created['id'], 'A pale tower with windows.', tokens['luna'])
        wait_for(self.store, 'guessing')
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)
        self.assertFalse(self.store.workers[created['id']].is_alive())
        self.assertEqual(self.store.get(created['id'])['phase'], 'cancelled')

    def test_ai_guess_failure_wakes_other_human_guesser(self):
        roster = self.human_roster()
        roster[1]['type'] = 'ai'
        def fail_guess(*args, **kwargs):
            raise RuntimeError('Test provider failed.')
        self.bridge.player = fail_guess
        created = self.store.create(players=roster)
        wait_for(self.store, 'awaiting_clue')
        token = next(row['token'] for row in created['invitations'] if row['playerId'] == 'luna')
        self.store.submit_clue(created['id'], 'A pale tower.', token)
        self.store.workers[created['id']].join(2)
        self.assertFalse(self.store.workers[created['id']].is_alive())
        self.assertEqual(self.store.get(created['id'])['phase'], 'error')

    def test_custom_goals_stay_private_and_use_custom_name_for_scoring(self):
        created = self.store.create(rounds=3, players=self.human_roster(), custom_goals=['Dragon', '', ''])
        wait_for(self.store, 'awaiting_clue')
        tokens = {row['playerId']: row['token'] for row in created['invitations']}
        self.assertNotIn('Dragon', json.dumps(self.store.get(created['id'])))
        self.assertEqual(self.store.get(created['id'], tokens['luna'])['privateAssignment']['name'], 'Dragon')
        with self.assertRaises(PermissionError):
            self.store.set_goal(created['id'], 'A castle', tokens['terra'])
        host_view = self.store.set_goal(created['id'], 'A castle', created['hostToken'])
        self.assertNotIn('privateAssignment', host_view)
        seat_view = self.store.set_goal(created['id'], 'A glass dragon', tokens['luna'])
        self.assertEqual(seat_view['privateAssignment']['name'], 'A glass dragon')
        self.store.submit_clue(created['id'], 'A winged reptile made from transparent material.', tokens['luna'])
        wait_for(self.store, 'guessing')
        self.assertEqual(self.bridge.known['target'], 'A glass dragon')
        with self.assertRaises(ValueError):
            self.store.set_goal(created['id'], 'Another goal', tokens['luna'])
        self.store.submit_guess(created['id'], 'glass dragon', tokens['terra'])
        self.store.submit_guess(created['id'], 'A glass dragon', tokens['sonnet'])
        wait_for(self.store, 'ready_to_reveal')
        state = self.store.reveal(created['id'], created['hostToken'])
        self.assertEqual(state['rounds'][0]['answer'], 'A glass dragon')
        self.assertEqual([player['score'] for player in state['players']], [2, 2, 2])
    def test_custom_goal_limits_and_lock_after_rejected_clue(self):
        with self.assertRaises(ValueError):
            self.store.create(rounds=1, custom_goals=['one', 'two'])
        with self.assertRaises(ValueError):
            self.store.create(rounds=1, custom_goals=['x' * 121])
        self.bridge.block_first = True
        created = self.store.create(rounds=1, players=self.human_roster(), custom_goals=['Dragon'])
        wait_for(self.store, 'awaiting_clue')
        token = created['invitations'][0]['token']
        self.store.submit_clue(created['id'], 'A reptile.', token)
        wait_for(self.store, 'awaiting_clue')
        with self.assertRaises(ValueError):
            self.store.set_goal(created['id'], 'A different goal', created['hostToken'])
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)

    def test_human_drawing_revisions_keep_previous_image_and_require_finish(self):
        self.store.draw_seconds = 60
        created = self.store.create(rounds=1, players=self.human_roster())
        wait_for(self.store, 'awaiting_clue')
        tokens = {item['playerId']: item['token'] for item in created['invitations']}
        self.store.submit_clue(created['id'], 'A tall pale tower.', tokens['luna'])
        state = wait_for(self.store, 'awaiting_clue')
        self.assertEqual(state['rounds'][0]['drawing']['version'], 1)
        self.assertTrue(state['rounds'][0]['drawing']['canFinish'])
        self.assertNotIn('clue', state['rounds'][0])
        self.assertIn('privateAssignment', self.store.get(created['id'], tokens['luna']))
        with self.assertRaises(ValueError):
            self.store.submit_guess(created['id'], 'Tower', tokens['terra'])
        with self.assertRaises(PermissionError):
            self.store.finish_drawing(created['id'], tokens['terra'])
        original = self.bridge.validate
        def blocked(target, clue):
            return {'verdict': 'block', 'reason': 'Remove the name.'}, {'usage': {}}
        self.bridge.validate = blocked
        self.store.submit_clue(created['id'], 'A named tower.', tokens['luna'])
        state = wait_for(self.store, 'awaiting_clue')
        self.assertEqual(state['rounds'][0]['drawing']['version'], 1)
        self.assertEqual(state['rounds'][0]['drawing']['attempts'][-1]['verdict'], 'block')
        self.assertEqual(state['rounds'][0]['promptAttempts'][-1]['verdict']['reason'], 'Remove the name.')
        self.assertEqual(state['rounds'][0]['promptAttempts'][-1]['clue'], 'A named tower.')
        self.assertNotIn('_target', json.dumps(state))
        self.assertNotIn('guesses', state['rounds'][0])
        self.assertEqual(self.store.get(created['id'], tokens['luna'])['privateFeedback'], 'Remove the name.')
        self.bridge.validate = original
        self.store.submit_clue(created['id'], 'A pale tower with a wide base.', tokens['luna'])
        state = wait_for(self.store, 'awaiting_clue')
        self.assertEqual(state['rounds'][0]['drawing']['version'], 2)
        self.store.finish_drawing(created['id'], tokens['luna'])
        wait_for(self.store, 'guessing')
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)

    def test_drawing_budget_pauses_during_provider_work(self):
        self.store.draw_seconds = .2
        gate = threading.Event()
        original = self.bridge.render_code
        def slow(*args, **kwargs):
            gate.wait(2)
            return original(*args, **kwargs)
        self.bridge.render_code = slow
        created = self.store.create(rounds=1, players=self.human_roster())
        wait_for(self.store, 'awaiting_clue')
        token = created['invitations'][0]['token']
        self.store.submit_clue(created['id'], 'A pale tower.', token)
        state = wait_for(self.store, 'rendering')
        before = state['rounds'][0]['drawing']['secondsRemaining']
        time.sleep(.3)
        state = self.store.get(created['id'])
        self.assertTrue(state['rounds'][0]['drawing']['paused'])
        self.assertEqual(state['rounds'][0]['drawing']['secondsRemaining'], before)
        gate.set()
        wait_for(self.store, 'guessing')
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)

    def test_default_four_contestants_and_muse_service(self):
        created = self.store.create()
        self.assertEqual([player['id'] for player in created['players']], ['luna', 'terra', 'sonnet', 'haiku'])
        self.assertEqual(created['artist']['id'], 'muse')
        self.assertEqual(created['totalRounds'], 4)
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)
    def test_competition_route_is_fixed_and_increases_difficulty(self):
        created = self.store.create(players=self.human_roster(), demo_route=True)
        state = self.store.games[created['id']]
        targets = [row['_target'] for row in state['rounds']]
        self.assertEqual(created['totalRounds'], 3)
        self.assertEqual([target['id'] for target in targets],
                         ['painted-ladies', 'borgund', 'rani-mahal'])
        self.assertEqual([target['difficulty'] for target in targets], [2, 3, 4])
        self.assertEqual([target['pool'] for target in targets], ['California', 'Norway', 'Nepal'])
        self.assertTrue(all(not target.get('custom') for target in targets))
        self.store.cancel(created['id'], created['hostToken'])
        self.store.workers[created['id']].join(2)

    def test_selection_increases_tiers_and_covers_three_regions(self):
        locations = [{'id': f'{country}-{tier}-{variant}', 'name': 'Place', 'region': country,
                      'country': country, 'difficulty': tier, 'aliases': []}
                     for country in ['California', 'Norway', 'Nepal']
                     for tier in range(1, 5) for variant in range(2)]
        chosen = select_locations(locations, 4)
        self.assertEqual([row['difficulty'] for row in chosen], [1, 2, 3, 4])
        self.assertEqual({row['country'] for row in chosen[:3]}, {'California', 'Norway', 'Nepal'})
        self.assertEqual(len({row['id'] for row in chosen}), 4)

    def test_matching_is_controlled_and_not_substring(self):
        target={'name':'Golden Gate Bridge','aliases':['Golden Gate']}
        self.assertTrue(is_correct('The Golden Gate Bridge',target))
        self.assertTrue(is_correct('Golden Gate',target))
        self.assertFalse(is_correct('Golden Gate or Bay Bridge',target))
        self.assertFalse(is_correct('bridge',target))

class AdapterTests(unittest.TestCase):
    def test_nepali_aliases_do_not_match_an_empty_signature(self):
        target = {'name': 'Boudhanath', 'region': 'Kathmandu', 'aliases': ['बौद्धनाथ', '!!!']}
        bridge = ModelBridge()
        with patch.object(bridge, 'openrouter', return_value=(
                '{"verdict":"allow","reason":"This describes visible shapes and materials."}', {})):
            result, metadata = bridge.validate(target, 'A great white dome with a square tower above it.')
        self.assertEqual(result['verdict'], 'allow')
        self.assertTrue(normalize_text('बौद्धनाथ'))
        self.assertEqual(normalize_text('Ålesund'), normalize_text('Ålesund'))

    def test_selected_openrouter_model_and_usage_are_preserved(self):
        selected = 'anthropic/claude-sonnet-5.5'
        response = {'model': selected, 'provider': 'Anthropic', 'id': 'generation-test',
                    'choices': [{'message': {'content': '{"guess":"A landmark"}'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'cost': 0.0002,
                              'prompt_tokens_details': {'cached_tokens': 20}}}
        with patch('model_bridge.config', return_value={'OPENROUTER_API_KEY': 'test-placeholder'}), \
             patch('model_bridge.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as opened:
            content, metadata = ModelBridge().openrouter([{'role': 'user', 'content': 'Guess.'}], model=selected, effort=None)
        payload = json.loads(opened.call_args.args[0].data)
        self.assertEqual(payload['model'], selected)
        self.assertNotIn('reasoning', payload)
        self.assertEqual(metadata['model'], selected)
        self.assertEqual(metadata['usage']['prompt_tokens_details']['cached_tokens'], 20)
    def test_mismatched_openrouter_model_rejected_with_usage(self):
        response = {'model': 'meta/muse-ember', 'choices': [{'message': {'content': '{}'}}], 'usage': {'cost': 0.001}}
        with patch('model_bridge.config', return_value={'OPENROUTER_API_KEY': 'test-placeholder'}), \
             patch('model_bridge.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaises(ProviderError) as caught:
                ModelBridge().openrouter([], model='anthropic/claude-haiku-5.5')
        self.assertEqual(caught.exception.metadata['usage']['cost'], 0.001)

if __name__=='__main__': unittest.main()
