import json
from test_reconstruction_pipeline import PipelineTestCase, write_json
from geometry_invariants import result_for


class InvariantControllerTests(PipelineTestCase):
    def test_cli_cannot_advance_without_current_passing_invariants(self):
        state_path, spec_path = self.initialize('simple')
        spec = json.loads(spec_path.read_text())
        invariant = {'id': 'equal-pane-size', 'featureId': 'feature-01',
            'measurement': 'pane', 'kind': 'dimensions', 'targets': ['L', 'R'],
            'frame': 'object-local', 'expected': [0.71, 0.0285, 3.49],
            'tolerance': 0.00001, 'applicablePasses': ['camera-match']}
        spec['geometryInvariants'] = [invariant]
        write_json(spec_path, spec)
        self.admit_intake(state_path, spec_path)
        renders, comparisons, views = self.evidence()
        report = self.critic_report('critic-invariants', 'context-invariants', 'continue', .91, None, 'ready', views)
        result = self.record_round(state_path, report, renders, comparisons, expected=2)
        self.assertIn('--invariant-report', result.stderr)
        state = json.loads(state_path.read_text())
        self.assertEqual('camera-match', state['currentPass'])
        current = next(p for p in state['passes'] if p['id'] == 'camera-match')
        self.assertEqual([], current['criticRounds'])
        checkpoint_hash = current['startCheckpoint']['sha256']
        invariant_report = {'schemaVersion': 2, 'passId': 'camera-match',
            'checkpointSha256': checkpoint_hash, 'specSha256': state['approvedContract']['sha256'],
            'errors': [], 'results': [result_for(invariant, {'L': [1,1,1], 'R': [1,1,1]})]}
        path = self.root / 'invariant-report.json'
        original_cli = self.run_cli
        def with_invariants(*args, expected=0):
            if args[0] == 'review': args = (*args, '--invariant-report', path)
            return original_cli(*args, expected=expected)
        self.run_cli = with_invariants
        write_json(path, invariant_report)
        self.record_round(state_path, report, renders, comparisons, expected=2)
        invariant_report['results'] = [result_for(invariant, {'L': invariant['expected'], 'R': invariant['expected']})]
        write_json(path, invariant_report)
        self.record_round(state_path, report, renders, comparisons)
        state = json.loads(state_path.read_text())
        self.assertEqual('blockout', state['currentPass'])
        current = next(p for p in state['passes'] if p['id'] == 'camera-match')
        self.assertEqual(str(path.resolve()), current['criticRounds'][0]['invariantReport']['path'])
