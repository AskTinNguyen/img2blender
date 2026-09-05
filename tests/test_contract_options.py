import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import contract_options as options
import reconstruction_pipeline as pipeline
from geometry_invariants import result_for


class ContractOptionsTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'subjectRoutes': ['hard-surface-prop'],
                     'featureContract': [{'featureId': 'opening'}],
                     'referenceAnalysis': {'observedFeatures': [{'id': 'opening'}]},
                     'references': [{'authority': 'design-proposal'}]}

    def inspection(self):
        return [{'featureId': 'opening', 'views': [{
            'role': 'section:opening', 'mode': 'section', 'proves': 'installed-fit',
            'retainedNeighbors': ['Leaf', 'Jamb']}]}]

    def test_legacy_defaults_preserve_full_evidence(self):
        self.assertEqual([], options.validate_options(self.spec))
        roles = pipeline.required_view_roles(self.spec, 'final-delivery')
        self.assertEqual(roles, pipeline.BASE_VIEW_ROLES)
        self.assertEqual({}, pipeline.required_view_roles(self.spec, 'intake'))
        self.spec['subjectRoutes'] = ['architecture-environment']
        roles = pipeline.required_view_roles(self.spec, 'final-delivery')
        self.assertTrue(set(pipeline.ARCHITECTURE_VIEW_ROLES) <= set(roles))

    def test_redesign_requires_authorization_and_reference_authority(self):
        self.spec['taskMode'] = 'creative-redesign'
        self.assertTrue(options.validate_options(self.spec))
        self.spec['designIntent'] = {'authorization': 'User allows redesign',
                                    'preservedRequirements': 'Equal openings',
                                    'allowedChanges': 'Ornament and finish'}
        self.assertEqual([], options.validate_options(self.spec))
        del self.spec['references'][0]['authority']
        self.assertTrue(options.validate_options(self.spec))

    def test_malformed_enums_and_ids_fail_without_type_crashes(self):
        for field in ('taskMode', 'validationScope'):
            with self.subTest(field=field):
                self.assertTrue(options.validate_options({**self.spec, field: []}))
        self.spec['references'][0]['authority'] = []
        self.assertTrue(options.validate_options(self.spec))
        self.spec['inspectionPlan'] = self.inspection()
        self.spec['featureContract'][0]['featureId'] = []
        self.spec['inspectionPlan'][0]['views'][0]['mode'] = []
        self.assertTrue(options.validate_options(self.spec))

    def test_scoped_component_requires_real_baseline_and_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'baseline.blend'; p.write_bytes(b'baseline')
            record = {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            self.spec['refinementScope'] = {'changedComponents': ['Leaf'],
                'affectedInterfaces': ['Leaf to frame'], 'baselineCheckpoint': record,
                'baselineEvidence': record, 'rationale': 'Only leaf changes'}
            self.assertTrue(options.validate_options(self.spec))
            self.spec['qualityContract'] = {'requiredViews': ['integration-context']}
            self.assertEqual([], options.validate_options(self.spec))
            self.assertIn('integration-context', pipeline.required_view_roles(self.spec, 'materials'))
            self.spec['subjectRoutes'] = ['architecture-environment']
            self.assertTrue(options.validate_options(self.spec))
            self.spec['subjectRoutes'] = ['hard-surface-prop']; p.write_bytes(b'changed')
            self.assertTrue(options.validate_options(self.spec))

    def test_isolated_fit_reserved_roles_and_missing_neighbors_rejected(self):
        self.spec['inspectionPlan'] = self.inspection()
        self.assertEqual([], options.validate_options(self.spec))
        for change in ({'mode': 'isolated'}, {'role': 'reference-overlay'},
                       {'retainedNeighbors': []}, {'proves': 'detail', 'retainedNeighbors': [['bad']]}):
            other = copy.deepcopy(self.spec)
            other['inspectionPlan'][0]['views'][0].update(change)
            self.assertTrue(options.validate_options(other), change)

    def test_inspection_provenance_cannot_substitute_isolation(self):
        self.spec['inspectionPlan'] = self.inspection()
        self.assertIn('section:opening', pipeline.required_view_roles(self.spec, 'materials'))
        manifest = {'renders': [{'role': 'section:opening', 'roleState': {'inspection': None}}]}
        with self.assertRaises(ValueError): options.validate_inspection_evidence(self.spec, manifest)
        actual = {'mode': 'section', 'disclosure': 'Section retains both neighbors',
                  'retainedNeighbors': ['Leaf', 'Jamb']}
        manifest['renders'][0]['roleState']['inspection'] = actual
        options.validate_inspection_evidence(self.spec, manifest)
        actual['retainedNeighbors'] = ['Leaf']
        with self.assertRaises(ValueError): options.validate_inspection_evidence(self.spec, manifest)
        actual['retainedNeighbors'] = ['Leaf', 'Jamb']; actual['mode'] = 'isolated'
        with self.assertRaises(ValueError): options.validate_inspection_evidence(self.spec, manifest)

    def invariant(self):
        return {'id': 'pane-size', 'featureId': 'opening', 'measurement': 'pane',
                'kind': 'dimensions', 'targets': ['L', 'R'], 'frame': 'object-local',
                'expected': [0.71, 0.0285, 3.49], 'tolerance': 0.00001}

    def test_controller_requires_report_and_recomputes_before_continue(self):
        self.spec['geometryInvariants'] = [self.invariant()]
        args = SimpleNamespace(action='continue', invariant_report=None)
        with self.assertRaisesRegex(ValueError, '--invariant-report'):
            pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials')
        args.action = 'refine-scene'
        self.assertIsNone(pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials'))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'invariants.json'
            row = self.invariant()
            result = result_for(row, {'L': [1, 1, 1], 'R': [1, 1, 1]})
            report = {'schemaVersion': 2, 'checkpointSha256': 'a'*64, 'specSha256': 'b'*64,
                      'passId': 'materials', 'results': [result], 'errors': []}
            p.write_text(json.dumps(report)); args.invariant_report = str(p)
            pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials')
            args.action = 'continue'
            with self.assertRaises(ValueError):
                pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials')
            result['pass'] = True; p.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials')
            report['results'] = [result_for(row, {'L': row['expected'], 'R': row['expected']})]
            p.write_text(json.dumps(report))
            self.assertIsNotNone(pipeline.validate_review_invariants(args, self.spec, {'sha256': 'a'*64}, 'b'*64, 'materials'))
            with self.assertRaises(ValueError):
                pipeline.validate_review_invariants(args, self.spec, {'sha256': 'c'*64}, 'b'*64, 'materials')

    def test_cli_exposes_additive_options(self):
        args = pipeline.build_parser().parse_args(['init', '--project-dir', '/tmp/example',
            '--name', 'doors', '--reference', '/tmp/reference.png',
            '--task-mode', 'creative-redesign', '--validation-scope', 'visual-asset'])
        self.assertEqual('creative-redesign', args.task_mode)


if __name__ == '__main__': unittest.main()
