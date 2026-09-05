"""Camera provenance must retain render-enabled neighboring objects, not just names."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class Camera(dict):
    name = 'Section camera'
    data = NS(type='PERSP')


class InspectionViewTests(unittest.TestCase):
    def setUp(self):
        fake_bpy = NS(context=NS(view_layer=NS(name='Review')))
        with patch.dict(sys.modules, {'bpy': fake_bpy}):
            spec = importlib.util.spec_from_file_location('inspection_renderer_test', ROOT / 'scripts/render_review_views.py')
            self.renderer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.renderer)
        self.obj = NS(name='Jamb', hide_render=False, visible_camera=True, is_holdout=False)
        self.layer = NS(exclude=False, indirect_only=False, holdout=False,
                        collection=NS(hide_render=False, objects=[self.obj]), children=[])
        view = NS(material_override=None, layer_collection=self.layer)
        self.scene = NS(view_layers={'Review': view})
        self.cam = Camera(img2blender_role='section:hinge', img2blender_inspection_mode='section',
                          img2blender_inspection_disclosure='Section retains jamb',
                          img2blender_retained_neighbors='["Jamb"]')

    def test_real_enabled_neighbor_is_recorded(self):
        state = self.renderer.role_state(self.scene, self.cam)
        self.assertEqual(['Jamb'], state['inspection']['retainedNeighbors'])
        self.assertEqual('section', state['inspection']['mode'])

    def test_hidden_holdout_and_camera_invisible_neighbors_are_rejected(self):
        for target, attr in [(self.obj, 'hide_render'), (self.obj, 'is_holdout'),
                             (self.layer, 'exclude'), (self.layer, 'indirect_only'),
                             (self.layer, 'holdout'), (self.layer.collection, 'hide_render')]:
            with self.subTest(attr=attr):
                setattr(target, attr, True)
                with self.assertRaises(ValueError): self.renderer.role_state(self.scene, self.cam)
                setattr(target, attr, False)
        self.obj.visible_camera = False
        with self.assertRaises(ValueError): self.renderer.role_state(self.scene, self.cam)

    def test_missing_disclosure_or_malformed_neighbors_fails(self):
        self.cam['img2blender_retained_neighbors'] = '[[]]'
        with self.assertRaises(ValueError): self.renderer.role_state(self.scene, self.cam)
        self.cam['img2blender_retained_neighbors'] = '["Missing"]'
        with self.assertRaises(ValueError): self.renderer.role_state(self.scene, self.cam)
        self.cam['img2blender_retained_neighbors'] = '["Jamb"]'
        self.cam['img2blender_inspection_disclosure'] = ''
        with self.assertRaises(ValueError): self.renderer.role_state(self.scene, self.cam)

if __name__ == '__main__': unittest.main()
